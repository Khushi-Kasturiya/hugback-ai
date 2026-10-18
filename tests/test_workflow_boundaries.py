"""Offline boundary evaluations; all Google/storage provider calls are mocked."""
import asyncio
import contextlib
import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from app.config import Settings, settings
from app.demo.models import CreateFamily
from app.demo.store import DemoStore
from app.main import app
from app.voice.profiles import VoiceProfileStore
from app.workflows.contracts import ConversationPlan, CritiqueReport
from app.workflows.critic import finish_quality_review
from scripts.migrate_env_names import migrate
from test_workflow import BASE, FakeFirestore, cloud_store


class CloudRouteTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        configuration = dict(
            LOCAL_DEMO_ENABLED=True, HUGBACK_DEMO_STORE="firestore",
            FIRESTORE_ENABLED=True, FIRESTORE_EMULATOR_HOST=None,
            HUGBACK_DEMO_PROJECT="synthetic-project", HUGBACK_DEMO_DATABASE="hugback-synthetic",
            HUGBACK_AUTH_MODE="firebase", FIREBASE_PROJECT_ID="synthetic-project",
            HUGBACK_CLOUD_TEST_ENABLED=True, HUGBACK_TEST_OWNER_UIDS="allowed-operator",
            HUGBACK_WORKFLOW_ENABLED=False, MEMORY_ENABLED=False, FOLLOWUPS_ENABLED=False,
            CLOUD_INTAKE_ENABLED=False, PORTAL_SHARING_ENABLED=False,
            HUGBACK_REPLICATED_TTS_ENABLED=False, HUGBACK_LIVE_VOICE_MODE="preset",
            HUGBACK_VOICE_DB_PATH=Path(temp.name) / "voice.sqlite3",
        )
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.multiple(settings, **configuration))
        self.stack.enter_context(patch.dict(os.environ, {"FIRESTORE_EMULATOR_HOST": ""}))
        self.store = cloud_store(FakeFirestore())
        self.stack.enter_context(patch("app.demo.routes.get_demo_store", return_value=self.store))
        self.stack.enter_context(patch("app.main.get_demo_store", return_value=self.store))
        self.verify = self.stack.enter_context(patch(
            "app.auth._verify_firebase_id_token", side_effect=lambda token: {"sub": token}))
        self.provider = self.stack.enter_context(patch("app.main.create_genai_client"))
        self.client = self.stack.enter_context(TestClient(app, client=("127.0.0.1", 1234)))
        self.headers = {"Origin": "http://127.0.0.1:3000", "Authorization": "Bearer allowed-operator"}

    def test_cloud_http_requires_firebase_allowlist_and_origin(self):
        denied = self.headers | {"Authorization": "Bearer stranger"}
        for path in ("/api/demo/family", "/api/portal/status", "/api/voice/profile"):
            self.assertEqual(self.client.get(path, headers=denied).status_code, 403)
        self.assertEqual(self.client.get("/api/demo/family", headers={
            "X-Hugback-Development-User": "allowed-operator"}).status_code, 401)
        for origin in ("https://untrusted.invalid", "http://127.0.0.1:9999"):
            self.assertEqual(self.client.post("/api/demo/family", headers=self.headers | {
                "Origin": origin}, json=BASE).status_code, 403)
        created = self.client.post("/api/demo/family", headers=self.headers, json=BASE)
        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["storageMode"], "firestore")
        self.assertEqual(created.json()["familyId"], self.store.get("firebase:allowed-operator")["familyId"])
        self.assertEqual(self.client.get("/api/portal/summaries", headers=self.headers).json(),
                         {"status": "synthetic_test_only", "summaries": []})
        self.provider.assert_not_called()

    def test_cloud_mode_blocks_legacy_routes_and_non_demo_websocket(self):
        for method, path, kwargs in (
            ("get", "/api/memories", {}), ("delete", "/api/memories", {}),
            ("post", "/internal/memory/process", {"json": {"user_id": "synthetic", "session_id": "session"}}),
        ):
            self.assertEqual(getattr(self.client, method)(path, headers=self.headers, **kwargs).status_code, 403)
        with self.client.websocket_connect("/ws", headers={"Origin": self.headers["Origin"]}) as ws:
            ws.send_json({"type": "authenticate", "idToken": "allowed-operator"})
            self.assertEqual(ws.receive_json()["type"], "error")
        self.provider.assert_not_called()

    def test_cloud_voice_owner_is_separate_from_development_owner(self):
        from app.voice.firestore_profiles import FirestoreVoiceProfileStore
        local_vault = VoiceProfileStore(settings.HUGBACK_VOICE_DB_PATH)
        local_vault.save("allowed-operator", "voicekey_syntheticDevelopmentKey")
        db = FakeFirestore()
        vault = FirestoreVoiceProfileStore(db)
        vault.firestore = SimpleNamespace(transactional=db.transactional)
        with (patch.object(settings, "HUGBACK_FIRESTORE_VOICE_RULES_CONFIRMED", True),
              patch("app.voice.routes.get_voice_store", return_value=vault)):
            # Neither local files nor development-scoped cloud profiles grant access.
            token = vault.begin_enrollment("allowed-operator")
            vault.save("allowed-operator", "voicekey_syntheticDevelopmentKey", enrollment_token=token)
            self.assertIsNone(self.client.get("/api/voice/profile", headers=self.headers).json()["profile"])
            token = vault.begin_enrollment("firebase:allowed-operator")
            own = vault.save("firebase:allowed-operator", "voicekey_syntheticFirebaseKey", enrollment_token=token)
            body = self.client.get("/api/voice/profile", headers=self.headers).json()
        self.assertEqual(body["profile"]["id"], own["id"])
        self.assertNotIn("voicekey", json.dumps(body))

    def test_remote_peer_cannot_use_test_routes(self):
        with TestClient(app, client=("192.0.2.9", 1234)) as remote:
            for path in ("/api/demo/family", "/api/portal/status", "/api/voice/profile"):
                self.assertEqual(remote.get(path, headers=self.headers).status_code, 403)


class QualityRaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_revoke_during_review_discards_report_and_next_call_can_start(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DemoStore(Path(directory) / "family.sqlite3")
            family = store.create("synthetic-owner", CreateFamily(**BASE))
            rid = family["recipients"][0]["recipientId"]
            state = store.start_call("synthetic-owner", "one", rid, 0)
            store.call_status(rid, "one", "completed", release=True, quality_pending=True)
            started, release = asyncio.Event(), asyncio.Event()

            async def review(*args, **kwargs):
                started.set()
                await release.wait()
                return CritiqueReport(), "completed"

            with patch("app.workflows.critic.review_call", new=review):
                task = asyncio.create_task(finish_quality_review(
                    store, rid, "one", state, [], [], "completed"))
                await asyncio.wait_for(started.wait(), 2)
                # Slow Critic must not hold the previous call's lease.
                store.start_call("synthetic-owner", "two", rid, 0)
                store.forget_background(rid)
                release.set()
                await asyncio.wait_for(task, 2)
            self.assertEqual(store.inspect_quality("synthetic-owner", rid), [])
            calls = store.get("synthetic-owner")["recipients"][0]["calls"]
            self.assertEqual(calls[0]["workflow"]["critic"], "privacy_skipped")

    async def test_privacy_before_review_blocks_provider_even_without_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DemoStore(Path(directory) / "family.sqlite3")
            family = store.create("synthetic-owner", CreateFamily(**(BASE | {"enableMemory": False})))
            rid = family["recipients"][0]["recipientId"]
            state = store.start_call("synthetic-owner", "one", rid, 0)
            store.workflow_checkpoint(rid, "one", {"critic": "completed"}, report=CritiqueReport(),
                                      revision=0, generation=state["memory"]["generation"])
            store.forget_background(rid)
            with patch("app.workflows.critic.review_call", new_callable=AsyncMock) as review:
                await finish_quality_review(store, rid, "one", state, [], [], "completed")
                review.assert_not_called()
            self.assertEqual(store.inspect_quality("synthetic-owner", rid), [])

    async def test_critic_failure_cannot_relabel_completed_call(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DemoStore(Path(directory) / "family.sqlite3")
            family = store.create("synthetic-owner", CreateFamily(**BASE))
            rid = family["recipients"][0]["recipientId"]
            state = store.start_call("synthetic-owner", "one", rid, 0)
            store.call_status(rid, "one", "completed", release=True, quality_pending=True)
            with patch("app.workflows.critic.review_call", new_callable=AsyncMock,
                       side_effect=RuntimeError("synthetic failure")):
                await finish_quality_review(store, rid, "one", state, [], [], "completed")
            call = store.get("synthetic-owner")["recipients"][0]["calls"][0]
            self.assertEqual(call["status"], "completed")
            self.assertEqual(call["workflow"]["critic"], "failed")


class ConfigurationAndEvalTests(unittest.TestCase):
    def test_offline_evals_do_not_inherit_live_storage_or_credentials(self):
        from evals.run import offline_environment
        with patch.dict(os.environ, {
            "GEMINI_API_KEY": "private-placeholder",
            "HUGBACK_DEMO_STORE": "firestore", "FIRESTORE_ENABLED": "TRUE",
            "FIRESTORE_EMULATOR_HOST": "127.0.0.1:8080", "HUGBACK_RUN_EMULATOR_TESTS": "1",
        }):
            env = offline_environment()
            self.assertEqual(env["GEMINI_API_KEY"], "synthetic-offline-key")
            self.assertEqual(env["HUGBACK_DEMO_STORE"], "sqlite")
            self.assertEqual(env["FIRESTORE_ENABLED"], "FALSE")
            self.assertEqual(env["FIRESTORE_EMULATOR_HOST"], "")
            self.assertEqual(env["HUGBACK_RUN_EMULATOR_TESTS"], "0")

    def test_emulator_endpoint_never_silently_redirects_other_modes(self):
        with patch.dict(os.environ, {"FIRESTORE_EMULATOR_HOST": ""}):
            for host in ("remote.invalid:8080", "127.0.0.1:8080/path",
                         "http://127.0.0.1:8080", "127.0.0.1:8080"):
                with self.subTest(host=host), self.assertRaises(ValueError):
                    Settings(_env_file=None, FIRESTORE_EMULATOR_HOST=host).validate_test_mode()

    def test_env_migration_preserves_values_and_refuses_conflicts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            original = '# private placeholder\nELARA_MODEL="synthetic-model"\nGEMINI_API_KEY=synthetic\n'
            path.write_text(original)
            self.assertEqual(migrate(path), [("ELARA_MODEL", "HUGBACK_MODEL")])
            self.assertEqual(path.read_text(), original)
            migrate(path, apply=True)
            self.assertEqual(path.read_text(), original.replace("ELARA_MODEL", "HUGBACK_MODEL"))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(migrate(path, apply=True), [])
            path.write_text(original + "HUGBACK_MODEL=another\n")
            with self.assertRaises(ValueError): migrate(path, apply=True)
            link = Path(directory) / "link"
            link.symlink_to(path)
            with self.assertRaises(ValueError): migrate(link)

    def test_paid_evals_reject_before_model_access(self):
        from evals.run import main
        with patch("evals.run.model_cases") as models, patch("evals.run.live_cases") as live:
            for suite in ("models", "live"):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                    main(["--suite", suite])
                self.assertEqual(error.exception.code, 2)
            models.assert_not_called()
            live.assert_not_called()

    def test_mocked_eval_report_contains_versions_scores_not_transcript(self):
        from evals.run import main
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            with patch("evals.run.model_cases", new_callable=AsyncMock, return_value=[
                {"id": "synthetic/case", "outcome": "pass"}]), contextlib.redirect_stdout(io.StringIO()):
                result = main(["--suite", "models", "--allow-paid-google", "--output", str(output)])
            report = json.loads(output.read_text())
            self.assertEqual(result, 0)
            self.assertEqual(report["counts"], {"pass": 1, "fail": 0, "error": 0})
            self.assertEqual(len(report["schemaSha256"]), 64)
            self.assertEqual(len(report["promptSha256"]), 64)
            self.assertNotIn("turns", report)
            self.assertNotIn("transcript", report)


class ModelEvalRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_model_suite_runs_with_mocked_google_adapter(self):
        from evals.run import DATA, model_cases
        from app.memory.followups import ObservationBatch
        data = json.loads(DATA.read_text())

        async def extract(_self, turns, plan):
            case = next(c for c in data["memory"] if c["text"] == turns[0].text)
            return ObservationBatch.model_validate({"observations": [{
                "topic": topic, "action": action, "source_turn": 0, "evidence": turns[0].text,
            } for topic, action in case["expected"]]})

        async def generate(_self, instruction, payload, schema, **kwargs):
            if schema is ConversationPlan:
                case = next(c for c in data["planner"]
                            if c["language"] == payload["language"]
                            and (not c["background"] and not payload["background"]
                                 or c["background"] and payload["background"]
                                 and c["background"][0]["text"] == payload["background"][0]["text"]))
                return ConversationPlan(language=payload["language"], background_refs=case["expectedRefs"])
            case = next(c for c in data["critic"] if c["assistant"] == payload["turns"][1]["text"])
            return CritiqueReport.model_validate({"findings": [{
                "code": code, "severity": "error", "source_turn": 1, "evidence": case["assistant"],
            } for code in case["expected"]]})

        saved = copy.deepcopy(settings.__dict__)
        try:
            with patch("app.memory.followup_extractor.GoogleFollowupExtractor.extract", new=extract), patch(
                    "app.workflows.provider.GoogleStructuredProvider.generate", new=generate):
                results = await model_cases(data)
            self.assertEqual(len(results), len(data["memory"]) + len(data["planner"]) + len(data["critic"]))
            self.assertTrue(all(r["outcome"] == "pass" for r in results), results)
        finally:
            settings.__dict__.clear()
            settings.__dict__.update(saved)
