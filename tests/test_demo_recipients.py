"""Multi-recipient isolation, migration and routing. Synthetic data, no Google I/O."""
import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from google.genai import types
from pydantic import ValidationError

from app.config import settings
from app.demo.models import CreateFamily, CreateRecipient, ReviewBackground, SelectRecipientVoice, SetTranscriptSharing
from app.demo.store import DemoStore, DemoError, now
from app.demo.summary import summary_input
from app.main import app
from app.memory.followups import FollowupState, ObservationBatch, record_consent, revoke
from app.memory.followup_service import FollowupCoordinator
from app.memory.models import TranscriptTurn
from app.voice.profiles import VoiceProfileStore
from app.workflows.planner import safe_local_bridge
from test_demo import HEADERS, ORIGIN, CREATE, review

OWNER = "synthetic-browser-a"


class RecipientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "demo.sqlite3"
        self.voices = VoiceProfileStore(Path(temp.name) / "voices.sqlite3")
        self.store = DemoStore(self.path)
        for name, value in {
            "LOCAL_DEMO_ENABLED": True, "HUGBACK_AUTH_MODE": "development", "HUGBACK_LIVE_VOICE_MODE": "preset",
            "HUGBACK_DEMO_STORE": "sqlite",
            "LOCAL_DEMO_DB_PATH": self.path, "HUGBACK_VOICE_DB_PATH": self.voices.path,
            "HUGBACK_REPLICATED_TTS_ENABLED": True, "GEMINI_API_KEY": "synthetic-placeholder",
            "HUGBACK_WORKFLOW_ENABLED": False,
        }.items():
            item = patch.object(settings, name, value); item.start(); self.addCleanup(item.stop)
        self.family = self.store.create(OWNER, CreateFamily(**CREATE, label="Mother", relationship="mother"))
        self.family = self.store.add_recipient(OWNER, CreateRecipient(**CREATE, label="Father", relationship="father"))
        self.mother, self.father = [r["recipientId"] for r in self.family["recipients"]]
        self.client = TestClient(app, client=("127.0.0.1", 1234))

    def recipient(self, rid):
        return next(r for r in self.store.get(OWNER)["recipients"] if r["recipientId"] == rid)

    def test_child_details_are_family_scoped_revisioned_and_used_by_future_calls(self):
        self.assertIsNone(self.store.get(OWNER)["childGender"])
        body = {"syntheticOnly": True, "familyId": self.family["familyId"],
                "revision": 0, "childName": "Asha", "childGender": "male"}
        response = self.client.put("/api/demo/child-details", headers=HEADERS, json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["childGender"], "male")
        self.assertEqual(response.json()["childName"], "Asha")
        self.assertEqual(response.json()["childGenderRevision"], 1)
        self.assertEqual(self.client.put("/api/demo/child-details", headers=HEADERS,
                         json={**body, "childGender": "female"}).status_code, 409)
        self.assertEqual(self.client.put("/api/demo/child-details", headers=HEADERS,
                         json={**body, "familyId": "demo-family-" + "0" * 32,
                               "revision": 1}).status_code, 404)
        state = self.store.start_call(OWNER, "gender-test", self.mother, 0)
        self.assertEqual(state["childGender"], "male")
        self.assertEqual(self.store.get(OWNER)["childName"], "Asha")
        self.store.call_status(self.mother, "gender-test", "completed", release=True)
        self.assertEqual(self.store.get(OWNER)["recipients"][1]["voice"]["mode"], "standard")

    def write_background(self, rid, text):
        return self.store.review(OWNER, ReviewBackground(**review(
            recipient=rid, revision=self.recipient(rid)["revision"], text=text,
        )))

    def auth(self, rid, **changes):
        return {"type": "authenticate", "userId": OWNER, "demoParent": True,
                "demoRecipientId": rid, "demoRecipientRevision": self.recipient(rid)["revision"], **changes}

    def test_recipients_have_distinct_ids_background_revisions_and_calls_after_restart(self):
        self.assertNotEqual(self.mother, self.father)
        self.write_background(self.mother, "Mother enjoys gardening.")
        self.write_background(self.father, "Father enjoys chess.")
        mother = self.recipient(self.mother); father = self.recipient(self.father)
        self.store.start_call(OWNER, "mother-call", self.mother, mother["revision"])
        self.store.start_call(OWNER, "father-call", self.father, father["revision"])
        self.store.call_status(self.mother, "mother-call", "completed", release=True)
        self.assertFalse(self.recipient(self.mother)["busy"])
        self.assertTrue(self.recipient(self.father)["busy"])
        self.assertFalse(self.store.call_status(self.mother, "father-call", "completed", release=True))
        with self.assertRaises(DemoError): self.store.clear(OWNER, self.father, father["revision"])
        self.store.clear(OWNER, self.mother, mother["revision"])
        restarted = DemoStore(self.path).get(OWNER)["recipients"]
        self.assertEqual(restarted[0]["background"], [])
        self.assertEqual(restarted[1]["background"][0]["text"], "Father enjoys chess.")
        self.assertEqual([r["calls"][0]["sessionId"] for r in restarted], ["mother-call", "father-call"])
        self.assertEqual(self.recipient(self.father)["revision"], father["revision"])
        self.assertNotIn("memory", restarted[0])

    def test_future_transcripts_require_standing_consent_and_stay_recipient_scoped(self):
        self.assertFalse(self.recipient(self.mother)["transcriptSharingEnabled"])
        with self.assertRaises(ValidationError):
            SetTranscriptSharing(syntheticOnly=True, recipientId=self.mother, revision=0,
                                 enabled=True, simulateChildConsent=True)
        consent = SetTranscriptSharing(syntheticOnly=True, recipientId=self.mother, revision=0,
                                       enabled=True, simulateChildConsent=True, simulateParentConsent=True)
        self.store.set_transcript_sharing(OWNER, consent)
        revision = self.recipient(self.mother)["revision"]
        self.store.start_call(OWNER, "session-mother", self.mother, revision)
        turns = [TranscriptTurn(role="user", turn_index=0, text="A fictional hello."),
                 TranscriptTurn(role="model", turn_index=1, text="Hello from HugBack.")]
        self.assertTrue(self.store.record_transcript(self.mother, "session-mother", 1, turns))
        self.assertTrue(self.store.record_call_summary(
            self.mother, "session-mother", 1,
            "Mother gave a fictional greeting and HugBack greeted her back."))
        self.store.call_status(self.mother, "session-mother", "completed", release=True)
        public = self.store.get(OWNER)
        self.assertEqual(public["recipients"][0]["calls"][0]["transcriptStatus"], "available")
        self.assertNotIn("transcript", public["recipients"][0]["calls"][0])
        with sqlite3.connect(self.path) as conn:
            stored = conn.execute("SELECT state FROM families").fetchone()[0]
        self.assertNotIn("A fictional hello.", stored)
        summary = self.store.get_call_summary(OWNER, self.mother, "session-mother")
        self.assertIn("fictional greeting", summary["summary"])
        self.assertNotIn("turns", summary)
        with self.assertRaises(DemoError): self.store.get_call_summary(OWNER, self.father, "session-mother")
        with self.assertRaises(DemoError): self.store.get_call_summary("synthetic-other", self.mother, "session-mother")
        self.store.set_transcript_sharing(OWNER, SetTranscriptSharing(
            syntheticOnly=True, recipientId=self.mother, revision=revision,
            enabled=False))
        with self.assertRaises(DemoError): self.store.get_call_summary(OWNER, self.mother, "session-mother")
        self.assertEqual(self.recipient(self.mother)["calls"][0]["transcriptStatus"], "revoked")
        self.assertEqual(self.recipient(self.mother)["calls"][0]["summaryStatus"], "revoked")

    def test_in_call_revocation_prevents_transcript_commit(self):
        self.store.set_transcript_sharing(OWNER, SetTranscriptSharing(
            syntheticOnly=True, recipientId=self.mother, revision=0, enabled=True,
            simulateChildConsent=True, simulateParentConsent=True))
        self.store.start_call(OWNER, "session-private", self.mother, 1)
        self.assertTrue(self.store.revoke_transcript_sharing(self.mother, 1))
        self.assertFalse(self.store.record_transcript(self.mother, "session-private", 1, [
            TranscriptTurn(role="user", turn_index=0, text="Keep this private.")]))
        self.assertFalse(self.store.record_call_summary(
            self.mother, "session-private", 1, "This private call should not be shared."))
        self.store.call_status(self.mother, "session-private", "completed", release=True)
        self.assertEqual(self.recipient(self.mother)["calls"][0]["transcriptStatus"], "revoked")

    def test_older_saved_text_can_be_converted_once_without_raw_response(self):
        self.store.set_transcript_sharing(OWNER, SetTranscriptSharing(
            syntheticOnly=True, recipientId=self.mother, revision=0, enabled=True,
            simulateChildConsent=True, simulateParentConsent=True))
        self.store.start_call(OWNER, "session-legacy", self.mother, 1)
        def seed_old_state(state):
            call = state["recipients"][0]["calls"][0]
            call.update(transcriptStatus="available", transcript=[
                {"role": "user", "text": "I painted blue flowers.", "timestamp": now().isoformat()},
                {"role": "model", "text": "That sounds lovely.", "timestamp": now().isoformat()},
            ])
            call.pop("summaryStatus", None)
        self.store._run(seed_old_state, uid=OWNER)
        self.store.call_status(self.mother, "session-legacy", "completed", release=True)
        self.assertTrue(self.recipient(self.mother)["calls"][0]["canGenerateLegacySummary"])
        with (patch("app.demo.routes.summarize_call", new=AsyncMock(
                  return_value="Mother discussed painting blue flowers with HugBack.")),
              TestClient(app, client=("127.0.0.1", 1234)) as client):
            response = client.post(f"/api/demo/summaries/{self.mother}/session-legacy/generate",
                                   headers=HEADERS, json={"syntheticOnly": True,
                                                          "recipientId": self.mother, "revision": 1})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn("I painted blue flowers.", response.text)
            self.assertEqual(client.get(f"/api/demo/summaries/{self.mother}/session-legacy",
                                        headers=HEADERS).json()["summary"],
                             "Mother discussed painting blue flowers with HugBack.")
        with sqlite3.connect(self.path) as conn:
            stored = conn.execute("SELECT state FROM families").fetchone()[0]
        self.assertNotIn('"transcript":', stored)
        self.assertFalse(self.recipient(self.mother)["calls"][0]["canGenerateLegacySummary"])

    def test_older_private_call_is_erased_without_model_conversion(self):
        self.store.set_transcript_sharing(OWNER, SetTranscriptSharing(
            syntheticOnly=True, recipientId=self.mother, revision=0, enabled=True,
            simulateChildConsent=True, simulateParentConsent=True))
        self.store.start_call(OWNER, "session-private-old", self.mother, 1)
        def seed_old_state(state):
            call = state["recipients"][0]["calls"][0]
            call.update(transcriptStatus="available", transcript=[
                {"role": "user", "text": "Do not share this conversation with my child.",
                 "timestamp": now().isoformat()},
            ])
            call.pop("summaryStatus", None)
        self.store._run(seed_old_state, uid=OWNER)
        self.store.call_status(self.mother, "session-private-old", "completed", release=True)
        with (patch("app.demo.routes.summarize_call", new=AsyncMock(
                  side_effect=AssertionError("No provider request on privacy revocation"))),
              TestClient(app, client=("127.0.0.1", 1234)) as client):
            response = client.post(f"/api/demo/summaries/{self.mother}/session-private-old/generate",
                                   headers=HEADERS, json={"syntheticOnly": True,
                                                          "recipientId": self.mother, "revision": 1})
            self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(self.recipient(self.mother)["transcriptSharingEnabled"])
        with sqlite3.connect(self.path) as conn:
            stored = conn.execute("SELECT state FROM families").fetchone()[0]
        self.assertNotIn("Do not share this conversation with my child.", stored)

    def test_oversized_transcript_is_never_exposed_as_partial_history(self):
        self.store.set_transcript_sharing(OWNER, SetTranscriptSharing(
            syntheticOnly=True, recipientId=self.mother, revision=0, enabled=True,
            simulateChildConsent=True, simulateParentConsent=True))
        self.store.start_call(OWNER, "session-long", self.mother, 1)
        self.assertFalse(self.store.record_transcript(self.mother, "session-long", 1, [
            TranscriptTurn(role="user", turn_index=0, text="x" * 25_001)]))
        self.store.call_status(self.mother, "session-long", "completed", release=True)
        self.assertEqual(self.recipient(self.mother)["calls"][0]["transcriptStatus"], "unavailable")
        with self.assertRaises(DemoError): self.store.get_call_summary(OWNER, self.mother, "session-long")

    def test_long_live_text_can_be_bounded_for_summary_without_saving_raw(self):
        self.store.set_transcript_sharing(OWNER, SetTranscriptSharing(
            syntheticOnly=True, recipientId=self.mother, revision=0, enabled=True,
            simulateChildConsent=True, simulateParentConsent=True))
        self.store.start_call(OWNER, "session-bounded", self.mother, 1)
        raw = [TranscriptTurn(role="user", turn_index=0, text="I painted today. " * 2000),
               TranscriptTurn(role="model", turn_index=1, text="Tell me more about your painting.")]
        self.assertTrue(self.store.record_transcript(
            self.mother, "session-bounded", 1, summary_input(raw)))
        self.store.call_status(self.mother, "session-bounded", "completed", release=True)
        call = self.recipient(self.mother)["calls"][0]
        self.assertEqual(call["transcriptStatus"], "available")
        with sqlite3.connect(self.path) as conn:
            stored = conn.execute("SELECT state FROM families").fetchone()[0]
        self.assertNotIn("I painted today.", stored)

    async def test_mothers_fever_is_not_fathers_memory_cooldown_resolution_or_privacy_scope(self):
        extractor = SimpleNamespace(extract=AsyncMock(return_value=ObservationBatch.model_validate({
            "observations": [{"topic": "fever", "action": "open", "source_turn": 0,
                              "evidence": "I feel feverish today."}],
        })))
        service = FollowupCoordinator(self.store, extractor)
        plan = await service.begin(self.mother, "mother-one")
        await service.finish(self.mother, plan, [TranscriptTurn(role="user", turn_index=0, text="I feel feverish today.")])
        father = await service.begin(self.father, "father-one")
        self.assertIsNone(father.selected)
        self.assertFalse((await service.claim(self.father, father, latest_user_text="Hello"))["allowed"])
        extractor.extract.return_value = ObservationBatch.model_validate({
            "observations": [{"topic": "fever", "action": "resolved", "source_turn": 0,
                              "evidence": "My fever has gone."}],
        })
        await service.finish(self.father, father, [
            TranscriptTurn(role="user", turn_index=0, text="My fever has gone."),
        ])
        self.assertEqual(self.recipient(self.mother)["memoryCount"], 1)
        mother = await service.begin(self.mother, "mother-two")
        self.assertEqual(mother.selected.topic, "fever")
        self.assertTrue((await service.claim(self.mother, mother, latest_user_text="Hello"))["allowed"])
        self.assertIsNone((await service.begin(self.mother, "mother-three")).selected)
        self.write_background(self.mother, "Mother's synthetic background.")
        self.write_background(self.father, "Father's synthetic background.")
        await self.store.transact(self.father, revoke)
        self.store.forget_background(self.father)
        self.assertFalse(self.recipient(self.father)["memoryEnabled"])
        self.assertTrue(self.recipient(self.mother)["memoryEnabled"])
        self.assertEqual(len(self.recipient(self.mother)["background"]), 2)
        self.assertEqual(self.recipient(self.mother)["memoryCount"], 1)
        self.assertIsNotNone((await service.begin(self.mother, "later", now=now() + timedelta(hours=25))).selected)

    def test_new_recipients_do_not_inherit_consent_or_history_and_labels_are_bounded(self):
        self.write_background(self.mother, "Synthetic history.")
        result = self.store.add_recipient(OWNER, CreateRecipient(**(CREATE | {"enableMemory": False}), label="Grandmother"))
        grandma = result["recipients"][-1]
        self.assertFalse(grandma["memoryEnabled"])
        self.assertEqual(grandma["background"], [])
        self.assertEqual(grandma["calls"], [])
        self.assertEqual(grandma["voice"]["mode"], "standard")
        for label in ("mother", "  Mother  "):
            with self.assertRaises(DemoError): self.store.add_recipient(OWNER, CreateRecipient(**CREATE, label=label))
        for label in (" ", "x" * 41, "bad\nlabel"):
            with self.assertRaises(ValidationError): CreateRecipient(**CREATE, label=label)
        for i in range(5): self.store.add_recipient(OWNER, CreateRecipient(**CREATE, label=f"Relative {i}"))
        with self.assertRaises(DemoError): self.store.add_recipient(OWNER, CreateRecipient(**CREATE, label="Overflow"))

    def test_public_mutations_and_ws_reject_foreign_missing_and_stale_recipient(self):
        other = self.store.create("synthetic-other", CreateFamily(**CREATE))
        foreign = other["recipients"][0]["recipientId"]
        for rid in (foreign, "demo-parent-" + "0" * 32):
            self.assertEqual(self.client.put("/api/demo/background", headers=HEADERS, json=review(recipient=rid)).status_code, 404)
            self.assertEqual(self.client.post("/api/demo/background/clear", headers=HEADERS, json={
                "syntheticOnly": True, "recipientId": rid, "revision": 0,
            }).status_code, 404)
            self.assertEqual(self.client.put("/api/demo/recipient-voice", headers=HEADERS, json={
                "syntheticOnly": True, "recipientId": rid, "revision": 0, "mode": "standard",
            }).status_code, 404)
        body = review(recipient=self.mother); del body["recipientId"]
        self.assertEqual(self.client.put("/api/demo/background", headers=HEADERS, json=body).status_code, 422)
        self.write_background(self.mother, "A new revision.")
        cases = [
            {"type": "authenticate", "userId": OWNER, "demoParent": True},
            self.auth(self.mother, demoRecipientId=foreign),
            self.auth(self.mother, demoRecipientRevision=0),
            self.auth(self.mother, demoRecipientRevision=True),
            self.auth(self.mother, demoParent=False),
        ]
        with patch("app.main.create_genai_client") as google:
            for envelope in cases:
                with self.client.websocket_connect("/ws", headers={"Origin": ORIGIN}) as ws:
                    ws.send_json(envelope)
                    self.assertEqual(ws.receive_json()["type"], "error")
            google.assert_not_called()
        self.assertFalse(self.recipient(self.mother)["busy"])
        self.assertEqual(self.recipient(self.father)["calls"], [])

    def test_shared_child_voice_assignments_remain_independent_and_owner_checked(self):
        profile = self.voices.save(OWNER, "voicekey_synthetic")
        self.voices.select(OWNER, profile["id"], True)
        self.assertEqual(self.client.put("/api/demo/recipient-voice", headers=HEADERS, json={
            "syntheticOnly": True, "recipientId": self.mother, "revision": 0,
            "mode": "child", "profileId": profile["id"], "speakingForm": "feminine",
        }).status_code, 422)
        for rid in (self.mother, self.father):
            response = self.client.put("/api/demo/recipient-voice", headers=HEADERS, json={
                "syntheticOnly": True, "recipientId": rid, "revision": 0, "mode": "child", "profileId": profile["id"],
            })
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.recipient(self.mother)["voice"], self.recipient(self.father)["voice"])
        self.client.put("/api/demo/recipient-voice", headers=HEADERS, json={
            "syntheticOnly": True, "recipientId": self.mother, "revision": 1, "mode": "standard",
        })
        self.assertEqual(self.recipient(self.father)["voice"]["mode"], "child")
        foreign_profile = self.voices.save("synthetic-other", "voicekey_foreign")
        self.voices.select("synthetic-other", foreign_profile["id"], True)
        self.assertEqual(self.client.put("/api/demo/recipient-voice", headers=HEADERS, json={
            "syntheticOnly": True, "recipientId": self.mother, "revision": 2, "mode": "child", "profileId": foreign_profile["id"],
        }).status_code, 409)
        replacement = self.voices.save(OWNER, "voicekey_replaced")
        self.voices.select(OWNER, replacement["id"], True)
        # Old assignment never silently acquires a different voice or uses preset.
        with patch("app.main.create_genai_client") as google:
            for changes in ({}, {"voiceProfileId": profile["id"]}, {"voiceProfileId": replacement["id"]}):
                with self.client.websocket_connect("/ws", headers={"Origin": ORIGIN}) as ws:
                    ws.send_json(self.auth(self.father, **changes))
                    self.assertEqual(ws.receive_json()["type"], "error")
            google.assert_not_called()
        self.assertFalse(self.recipient(self.father)["busy"])


    async def test_v1_migration_preserves_ids_memory_background_active_lease_without_guessing_identity(self):
        path = self.path.parent / "legacy.sqlite3"
        parent_id = "demo-parent-" + "a" * 32
        memory = FollowupState(time_zone="Asia/Kolkata")
        record_consent(memory, version="synthetic-v1", source="local_simulator_not_verified_parent", time_zone="Asia/Kolkata", now=now())
        old = {"familyId": "demo-family-old", "childId": "demo-child-old", "parentId": parent_id,
               "timeZone": "Asia/Kolkata", "expiresAt": (now() + timedelta(days=2)).isoformat(),
               "revision": 5, "background": [{"text": "Legacy fictional gardening."}],
               "calls": [{"sessionId": "existing-call", "status": "processing"}],
               "activeCall": {"sessionId": "existing-call", "leaseUntil": (now() + timedelta(minutes=5)).isoformat()},
               "memory": memory.model_dump(mode="json")}
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE families (owner TEXT PRIMARY KEY, parent TEXT UNIQUE NOT NULL, state TEXT NOT NULL)")
            conn.execute("INSERT INTO families VALUES (?,?,?)", (DemoStore.owner(OWNER), parent_id, json.dumps(old)))
        migrated = DemoStore(path)
        result = migrated.get(OWNER)
        self.assertEqual(result["familyId"], old["familyId"])
        self.assertEqual(result["childId"], old["childId"])
        recipient = result["recipients"][0]
        self.assertEqual(recipient["recipientId"], parent_id)
        self.assertEqual(recipient["label"], "Existing parent")
        self.assertEqual(recipient["revision"], 5)
        self.assertTrue(recipient["busy"])
        self.assertEqual(recipient["voice"]["mode"], "standard")
        await migrated.transact(parent_id, lambda state: self.assertTrue(state.consent))
        self.assertTrue(migrated.call_status(parent_id, "existing-call", "completed", release=True))
        second = migrated.add_recipient(OWNER, CreateRecipient(**CREATE, label="Mother", relationship="mother"))
        self.assertEqual(second["recipients"][0]["background"], old["background"])
        self.assertEqual(second["recipients"][1]["background"], [])
        self.assertEqual(len(DemoStore(path).get(OWNER)["recipients"]), 2)
        with sqlite3.connect(path) as conn:
            stored = json.loads(conn.execute("SELECT state FROM families").fetchone()[0])
        self.assertNotIn("parentId", stored)
        self.assertEqual(stored["schemaVersion"], 2)

    def test_mock_broker_calls_route_only_selected_context_and_private_finalizers(self):
        self.write_background(self.mother, "I enjoy fictional orchids.")
        self.write_background(self.father, "I enjoy fictional chess.")
        self.store.set_transcript_sharing(OWNER, SetTranscriptSharing(
            syntheticOnly=True, recipientId=self.mother,
            revision=self.recipient(self.mother)["revision"], enabled=True,
            simulateChildConsent=True, simulateParentConsent=True))
        captured, owners, finished = [], [], threading.Event()
        class Live:
            def __init__(self): self.queue = asyncio.Queue()
            async def send_client_content(self, **kwargs):
                await self.queue.put(types.LiveServerMessage(server_content=types.LiveServerContent(
                    output_transcription=types.Transcription(text="I am Hugback, an AI companion."), turn_complete=True,
                )))
            async def receive(self): yield await self.queue.get()
        @asynccontextmanager
        async def connect(*, model, config):
            captured.append(config.system_instruction.parts[0].text)
            yield Live()
        async def begin(owner, session):
            from app.memory.followups import CallPlan
            owners.append(owner)
            return CallPlan(session_id=session, generation=1, consent=False, time_zone="Asia/Kolkata")
        async def finish(owner, plan, turns):
            owners.append(owner); finished.set(); return "skipped"
        coordinator = SimpleNamespace(begin=AsyncMock(side_effect=begin), finish=AsyncMock(side_effect=finish))
        profile = self.voices.save(OWNER, "voicekey_synthetic"); self.voices.select(OWNER, profile["id"], True)
        # The global child voice is enabled, but both explicit recipient choices
        # are standard. They must remain callable without a key or TTS request.
        with (
            patch("app.main.create_genai_client", return_value=SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))),
            patch("app.main.summarize_call", new=AsyncMock(return_value="Mother greeted HugBack and received a friendly reply.")),
            patch("app.main.get_demo_coordinator", return_value=coordinator),
            patch("app.main.get_session_store", side_effect=AssertionError("No cloud")),
            patch("app.voice.playback.stream_replicated_speech", side_effect=AssertionError("No custom TTS")),
            patch("app.main.prepare_call", new=AsyncMock(
                side_effect=lambda state, _followup: (safe_local_bridge(state), "fallback")
            )),
            patch.object(settings, "HUGBACK_WORKFLOW_ENABLED", True),
            TestClient(app, client=("127.0.0.1", 1234)) as client,
        ):
            for rid in (self.mother, self.father):
                finished.clear()
                with client.websocket_connect("/ws", headers={"Origin": ORIGIN}) as ws:
                    ws.send_json(self.auth(rid))
                    ready = ws.receive_json()
                    self.assertEqual(ready["demo"]["recipientId"], rid)
                    self.assertEqual(ready["voice"], "default")
                    ws.send_json({"type": "text", "text": "Synthetic hello."})
                    while not ws.receive_json().get("turnComplete"): pass
                self.assertTrue(finished.wait(2))
            mother_call = self.recipient(self.mother)["calls"][0]
            deadline = time.monotonic() + 2
            while mother_call["transcriptStatus"] == "pending" and time.monotonic() < deadline:
                time.sleep(0.01); mother_call = self.recipient(self.mother)["calls"][0]
            self.assertEqual(mother_call["transcriptStatus"], "available")
            deadline = time.monotonic() + 2
            while mother_call.get("summaryStatus") == "pending" and time.monotonic() < deadline:
                time.sleep(0.01); mother_call = self.recipient(self.mother)["calls"][0]
            self.assertEqual(mother_call["summaryStatus"], "available")
            response = client.get(f"/api/demo/summaries/{self.mother}/{mother_call['sessionId']}", headers=HEADERS)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn("summary", response.json())
            self.assertNotIn("turns", response.json())
            self.assertEqual(client.get(f"/api/demo/transcripts/{self.mother}/{mother_call['sessionId']}",
                                        headers=HEADERS).status_code, 404)
            self.assertEqual(client.get(f"/api/demo/summaries/{self.father}/{mother_call['sessionId']}", headers=HEADERS).status_code, 403)
            self.assertEqual(client.get(f"/api/demo/summaries/{self.mother}/{mother_call['sessionId']}",
                                        headers=HEADERS | {"X-Hugback-Development-User": "someone-else"}).status_code, 404)
        self.assertEqual(owners, [self.mother, self.mother, self.father, self.father])
        self.assertIn("fictional orchids", captured[0]); self.assertNotIn("fictional chess", captured[0])
        self.assertIn("fictional chess", captured[1]); self.assertNotIn("fictional orchids", captured[1])
        self.assertIn('"recipient_label": "Mother"', captured[0])
        self.assertIn('"recipient_label": "Father"', captured[1])
