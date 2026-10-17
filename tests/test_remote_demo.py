"""Hosted demo boundary tests. Firebase, Firestore and Google AI are mocked."""
import asyncio
import contextlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.config import Settings, settings
from app.main import app
from test_workflow import BASE, FakeFirestore, cloud_store

ORIGIN = "https://demo.example"
CONFIG = dict(
    LOCAL_DEMO_ENABLED=True, HUGBACK_DEMO_STORE="firestore",
    FIRESTORE_ENABLED=True, FIRESTORE_EMULATOR_HOST=None,
    HUGBACK_DEMO_PROJECT="synthetic-project", HUGBACK_DEMO_DATABASE="hugback-synthetic",
    FIREBASE_PROJECT_ID="synthetic-project", HUGBACK_AUTH_MODE="firebase",
    HUGBACK_CLOUD_TEST_ENABLED=True, HUGBACK_REMOTE_TEST_ENABLED=True,
    HUGBACK_REMOTE_TEST_ORIGIN=ORIGIN, HUGBACK_PUBLIC_DEMO_ENABLED=True,
    HUGBACK_TEST_OWNER_UIDS="", CORS_ORIGINS=ORIGIN,
    HUGBACK_WORKFLOW_ENABLED=False, MEMORY_ENABLED=False, FOLLOWUPS_ENABLED=False,
    CLOUD_INTAKE_ENABLED=False, PORTAL_SHARING_ENABLED=False,
    HUGBACK_REPLICATED_TTS_ENABLED=False, HUGBACK_LIVE_VOICE_MODE="preset",
    HUGBACK_FIRESTORE_VOICE_RULES_CONFIRMED=False,
    HUGBACK_ALERT_EMAIL_ENABLED=False,
)


class RemoteConfigurationTests(unittest.TestCase):
    def test_public_and_restricted_modes_are_explicit(self):
        with patch.dict(os.environ, {"FIRESTORE_EMULATOR_HOST": ""}):
            Settings(_env_file=None, **CONFIG).validate_test_mode()
            Settings(_env_file=None, **(CONFIG | {
                "HUGBACK_REPLICATED_TTS_ENABLED": True,
                "HUGBACK_FIRESTORE_VOICE_RULES_CONFIRMED": True,
            })).validate_test_mode()
            Settings(_env_file=None, **(CONFIG | {
                "HUGBACK_PUBLIC_DEMO_ENABLED": False, "HUGBACK_TEST_OWNER_UIDS": "tester-a,tester-b",
            })).validate_test_mode()
            for changes in (
                {"HUGBACK_REMOTE_TEST_ENABLED": False},
                {"HUGBACK_PUBLIC_DEMO_ENABLED": False},
                {"LOCAL_DEMO_ENABLED": False},
                {"FIRESTORE_ENABLED": False},
                {"HUGBACK_DEMO_STORE": "sqlite"},
                {"FIRESTORE_EMULATOR_HOST": "127.0.0.1:8080"},
                {"HUGBACK_CLOUD_TEST_ENABLED": False},
                {"HUGBACK_AUTH_MODE": "development"},
                {"FIREBASE_PROJECT_ID": "other-project"},
                {"HUGBACK_DEMO_DATABASE": "(default)"},
                {"HUGBACK_REPLICATED_TTS_ENABLED": True},
                {"HUGBACK_LIVE_VOICE_MODE": "experimental-inline"},
                {"HUGBACK_ALERT_EMAIL_ENABLED": True},
                {"MEMORY_ENABLED": True},
                {"FOLLOWUPS_ENABLED": True},
                {"CLOUD_INTAKE_ENABLED": True},
                {"PORTAL_SHARING_ENABLED": True},
                {"CORS_ORIGINS": "*"},
            ):
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    Settings(_env_file=None, **(CONFIG | changes)).validate_test_mode()

    def test_remote_origins_and_restricted_uid_lists_fail_closed(self):
        with patch.dict(os.environ, {"FIRESTORE_EMULATOR_HOST": ""}):
            for origin in ("", "http://demo.example", "https://localhost",
                           "https://demo.example/", "https://demo.example/path",
                           "https://demo.example?x=1", "https://demo.example#fragment",
                           "https://user:pass@demo.example", "https://*.example",
                           "https://demo.example:bad", "https://demo.example:99999",
                           "https://other.example"):
                with self.subTest(origin=origin), self.assertRaises(ValueError):
                    Settings(_env_file=None, **(CONFIG | {"HUGBACK_REMOTE_TEST_ORIGIN": origin})).validate_test_mode()
            for uids in ("", "*", "firebase:tester-a", "tester-a,", ",", "tester-a,,tester-b"):
                with self.subTest(uids=uids), self.assertRaises(ValueError):
                    Settings(_env_file=None, **(CONFIG | {
                        "HUGBACK_PUBLIC_DEMO_ENABLED": False, "HUGBACK_TEST_OWNER_UIDS": uids,
                    })).validate_test_mode()


class RemoteRouteTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        temp = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.stack.enter_context(patch.multiple(
            settings, **CONFIG, HUGBACK_VOICE_DB_PATH=Path(temp) / "voice.sqlite3",
        ))
        self.stack.enter_context(patch.dict(os.environ, {"FIRESTORE_EMULATOR_HOST": ""}))
        self.store = cloud_store(FakeFirestore())
        self.stack.enter_context(patch("app.demo.routes.get_demo_store", return_value=self.store))
        self.stack.enter_context(patch("app.main.get_demo_store", return_value=self.store))
        self.stack.enter_context(patch(
            "app.auth._verify_firebase_id_token", side_effect=lambda token: {"sub": token},
        ))
        self.provider = self.stack.enter_context(patch("app.main.create_genai_client"))
        self.vault = self.stack.enter_context(patch("app.portal.routes.get_voice_store"))
        self.client = self.stack.enter_context(TestClient(app, client=("192.0.2.9", 1234)))
        self.headers = {"Origin": ORIGIN, "Authorization": "Bearer new-visitor-a"}

    def create(self, headers=None):
        response = self.client.post("/api/demo/family", headers=headers or self.headers,
                                    json=BASE | {"enableMemory": False})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_new_verified_visitors_do_not_need_a_preknown_uid(self):
        status = self.client.get("/api/portal/status", headers=self.headers)
        self.assertEqual(status.status_code, 200)
        self.assertTrue(status.json()["publicDemoEnabled"])
        self.assertFalse(status.json()["voice"]["replicatedTtsEnabled"])
        self.assertIsNone(status.json()["voice"]["profile"])
        a = self.create()
        other_headers = self.headers | {"Authorization": "Bearer new-visitor-b"}
        b = self.create(other_headers)
        self.assertNotEqual(a["familyId"], b["familyId"])
        fetched = self.client.get("/api/demo/family?userId=new-visitor-a", headers=other_headers)
        self.assertEqual(fetched.json()["familyId"], b["familyId"])
        rid = a["recipients"][0]["recipientId"]
        denied = self.client.put("/api/demo/recipient-voice", headers=other_headers,
                                 json={"syntheticOnly": True, "recipientId": rid, "revision": 0, "mode": "standard"})
        self.assertIn(denied.status_code, (403, 404))
        summary = self.client.get(f"/api/demo/summaries/{rid}/session-fictional", headers=other_headers)
        self.assertIn(summary.status_code, (403, 404))
        self.provider.assert_not_called()
        self.vault.assert_not_called()

    def test_token_and_exact_origin_remain_mandatory(self):
        for path in ("/api/demo/family", "/api/portal/status"):
            for origin in (None, "null", "http://demo.example", "https://demo.example.evil.invalid",
                           ORIGIN + "/", "http://127.0.0.1:3000"):
                headers = {"Authorization": "Bearer new-visitor-a", "X-Forwarded-For": "127.0.0.1",
                           "X-Forwarded-Host": "demo.example"}
                if origin is not None:
                    headers["Origin"] = origin
                self.assertEqual(self.client.get(path, headers=headers).status_code, 403)
            self.assertEqual(self.client.get(path, headers={"Origin": ORIGIN,
                "X-Hugback-Development-User": "new-visitor-a"}).status_code, 401)
            with patch("app.auth._verify_firebase_id_token", side_effect=ValueError):
                self.assertEqual(self.client.get(path, headers=self.headers).status_code, 401)
        self.provider.assert_not_called()

    def test_restricted_mode_and_remote_off_switch_still_work(self):
        with patch.multiple(settings, HUGBACK_PUBLIC_DEMO_ENABLED=False,
                            HUGBACK_TEST_OWNER_UIDS="approved"):
            self.assertEqual(self.client.get("/api/portal/status", headers=self.headers).status_code, 403)
            self.assertEqual(self.client.get("/api/portal/status", headers=self.headers | {
                "Authorization": "Bearer approved"}).status_code, 200)
        with patch.multiple(settings, HUGBACK_PUBLIC_DEMO_ENABLED=False,
                            HUGBACK_REMOTE_TEST_ENABLED=False, HUGBACK_TEST_OWNER_UIDS="new-visitor-a"):
            self.assertEqual(self.client.get("/api/portal/status", headers=self.headers).status_code, 403)

    def test_remote_demo_never_exposes_voice_vault_or_legacy_memory(self):
        for path in ("/api/voice/profile", "/api/memories"):
            self.assertEqual(self.client.get(path, headers=self.headers).status_code, 403)
        self.assertEqual(self.client.post("/api/voice/enroll", headers=self.headers, json={
            "voiceSampleAudio": "AAAA", "consentAudio": "AAAA", "adultOwnVoice": True,
            "consentToGoogleAndBilling": True,
        }).status_code, 403)
        self.assertEqual(self.client.get("/api/portal/summaries", headers=self.headers).json(),
                         {"status": "synthetic_test_only", "summaries": []})
        self.provider.assert_not_called()
        self.vault.assert_not_called()

    def test_websocket_denies_foreign_recipient_revision_origin_and_unscoped_call(self):
        recipient = self.create()["recipients"][0]
        valid = {"type": "authenticate", "idToken": "new-visitor-a", "demoParent": True,
                 "demoRecipientId": recipient["recipientId"], "demoRecipientRevision": recipient["revision"]}
        for origin, message in (
            (ORIGIN, valid | {"idToken": "new-visitor-b"}),
            (ORIGIN, valid | {"demoRecipientRevision": 99}),
            ("https://other.example", valid),
            (None, valid),
            (ORIGIN, {"type": "authenticate", "idToken": "new-visitor-a"}),
            (ORIGIN, valid | {"voiceProfileId": "a" * 32}),
        ):
            with self.subTest(origin=origin, fields=list(message)):
                with self.client.websocket_connect("/ws", headers={"Origin": origin} if origin else {}) as ws:
                    ws.send_json(message)
                    self.assertEqual(ws.receive_json()["type"], "error")
        self.provider.assert_not_called()

    def test_own_standard_voice_websocket_can_reach_ready_without_paid_io(self):
        recipient = self.create()["recipients"][0]
        class Live:
            async def receive(self):
                await asyncio.Event().wait()
                yield  # Never reached: the browser disconnects without a call turn.
        @contextlib.asynccontextmanager
        async def connect(**kwargs):
            yield Live()
        self.provider.return_value = SimpleNamespace(
            aio=SimpleNamespace(live=SimpleNamespace(connect=connect), aclose=AsyncMock()),
            close=lambda: None,
        )
        with self.client.websocket_connect("/ws", headers={"Origin": ORIGIN}) as ws:
            ws.send_json({"type": "authenticate", "idToken": "new-visitor-a", "demoParent": True,
                          "demoRecipientId": recipient["recipientId"],
                          "demoRecipientRevision": recipient["revision"]})
            ready = ws.receive_json()
            self.assertEqual(ready["type"], "ready", ready)
            self.assertEqual(ready["voice"], "default")
        self.provider.assert_called_once()
