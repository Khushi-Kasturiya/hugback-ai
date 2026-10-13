"""Synthetic voice-cue continuity stays separate from speaker identity and child signals."""

import asyncio
import tempfile
import time
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from google.genai import types
from pydantic import ValidationError

from app.config import settings
from app.demo.models import CreateFamily, CreateRecipient, SetToneContinuity
from app.demo.store import DemoError, DemoStore
from app.main import app
from app.memory.followups import CallPlan
from app.memory.models import TranscriptTurn
from app.wellbeing.models import WellbeingSignalDraft
from app.wellbeing.service import SignalCollector, contains_tone_privacy_request, tone_context


BASE = {"syntheticOnly": True, "simulateChildConsent": True, "simulateParentConsent": True}


class ToneContinuityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = DemoStore(Path(temp.name) / "demo.sqlite3")
        family = self.store.create("child-one", CreateFamily(
            **BASE, label="Mumma", relationship="mother",
        ))
        family = self.store.add_recipient("child-one", CreateRecipient(
            **BASE, label="Papa", relationship="father",
        ))
        self.mumma, self.papa = [r["recipientId"] for r in family["recipients"]]

    def recipient(self, recipient_id):
        return next(r for r in self.store.get("child-one")["recipients"]
                    if r["recipientId"] == recipient_id)

    def enable(self):
        return self.store.set_tone_continuity("child-one", SetToneContinuity(
            syntheticOnly=True, recipientId=self.mumma,
            revision=self.recipient(self.mumma)["revision"], enabled=True,
            simulateChildConsent=True, simulateParentConsent=True,
        ))

    def test_separate_consent_and_no_cross_recipient_or_child_read(self):
        with self.assertRaises(ValidationError):
            CreateRecipient(**BASE, label="Aunt", enableToneContinuity=True)
        with self.assertRaises(ValidationError):
            SetToneContinuity(syntheticOnly=True, recipientId=self.mumma,
                              revision=0, enabled=True)
        self.enable()
        self.assertFalse(self.store.inspect_tone("child-one", self.mumma)["activeNote"])
        state = self.store.start_call("child-one", "call-tone-one", self.mumma,
                                      self.recipient(self.mumma)["revision"])
        generation = state["toneContinuity"]["generation"]
        weak = WellbeingSignalDraft(category="lower_energy", confidence="medium", basis=["vocal_cues"])
        content_only = WellbeingSignalDraft(category="lower_energy", confidence="high", basis=["conversation_content"])
        strong = WellbeingSignalDraft(category="lower_energy", confidence="high", basis=["vocal_cues"])
        self.assertFalse(self.store.record_tone_observation(self.mumma, "call-tone-one", generation, weak))
        self.assertFalse(self.store.record_tone_observation(self.mumma, "call-tone-one", generation, content_only))
        self.assertFalse(self.store.record_tone_observation(self.papa, "call-tone-one", generation, strong))
        self.assertTrue(self.store.record_tone_observation(self.mumma, "call-tone-one", generation, strong))
        inspected = self.store.inspect_tone("child-one", self.mumma)
        self.assertEqual((inspected["activeNote"], inspected["category"], inspected["confidence"]),
                         (True, "lower_energy", "high"))
        self.assertNotIn("basis", inspected)
        with self.assertRaises(DemoError):
            self.store.inspect_tone("another-child", self.mumma)
        public = self.recipient(self.mumma)
        self.assertTrue(public["toneContinuityEnabled"])
        self.assertNotIn("toneObservation", public)
        self.assertEqual(self.recipient(self.papa)["wellbeingSignals"], [])
        self.assertFalse(self.store.record_tone_observation(self.mumma, "wrong-call", generation, strong))
        self.store.call_status(self.mumma, "call-tone-one", "completed", release=True)
        next_state = self.store.start_call("child-one", "call-tone-two", self.mumma,
                                           self.recipient(self.mumma)["revision"])
        self.assertIn("lower_energy", tone_context(next_state))
        self.store.call_status(self.mumma, "call-tone-two", "completed", release=True)
        third_state = self.store.start_call("child-one", "call-tone-three", self.mumma,
                                            self.recipient(self.mumma)["revision"])
        self.assertIn("none", tone_context(third_state))
        self.assertEqual(tone_context(self.store.start_call(
            "child-one", "call-papa", self.papa, self.recipient(self.papa)["revision"])), "")

    def test_stop_erases_note_and_blocks_stale_writes(self):
        self.enable()
        state = self.store.start_call("child-one", "call-tone", self.mumma,
                                      self.recipient(self.mumma)["revision"])
        generation = state["toneContinuity"]["generation"]
        draft = WellbeingSignalDraft(category="upbeat", confidence="high", basis=["vocal_cues"])
        self.assertTrue(self.store.record_tone_observation(self.mumma, "call-tone", generation, draft))
        self.assertTrue(self.store.revoke_tone_continuity(self.mumma, generation))
        self.assertFalse(self.store.inspect_tone("child-one", self.mumma)["activeNote"])
        self.assertFalse(self.store.record_tone_observation(self.mumma, "call-tone", generation, draft))
        self.assertEqual(tone_context(self.store._run(lambda family: next(
            r for r in family["recipients"] if r["recipientId"] == self.mumma), uid="child-one")), "")

    def test_expired_or_unclear_observation_is_not_prompted(self):
        state = {"toneContinuity": {"enabled": True}, "toneObservation": {
            "category": "tense", "expiresAt": "2020-01-01T00:00:00+00:00",
        }}
        self.assertIn("none", tone_context(state))
        for phrase in ("Please don't analyze my voice.", "Stop tone check-ins.",
                       "Meri awaaz ko mat analyze karo."):
            self.assertTrue(contains_tone_privacy_request([
                TranscriptTurn(role="user", text=phrase, turn_index=0),
            ]))

    def test_short_or_text_only_call_does_not_leave_tone_note(self):
        collector = SignalCollector(enabled=True)
        collector.propose({"category": "lower_energy", "confidence": "high", "basis": ["vocal_cues"]})
        self.assertIsNone(collector.tone_publishable([
            TranscriptTurn(role="user", text="Hello.", turn_index=0),
        ]))
        collector.propose({"category": "lower_energy", "confidence": "high", "basis": ["conversation_content"]})
        self.assertIsNone(collector.tone_publishable([
            TranscriptTurn(role="user", text="A fictional long day with some ordinary things.", turn_index=0),
            TranscriptTurn(role="user", text="Then I rested and talked for a while.", turn_index=1),
        ]))

    def test_mock_live_call_saves_private_tone_note_without_child_signal(self):
        self.enable()

        class Live:
            def __init__(self):
                self.queue = asyncio.Queue()

            async def send_client_content(self, **kwargs):
                await self.queue.put(types.LiveServerMessage(tool_call=types.LiveServerToolCall(
                    function_calls=[types.FunctionCall(
                        id="tone", name="propose_call_wellbeing_signal",
                        args={"category": "lower_energy", "confidence": "high", "basis": ["vocal_cues"]},
                    )],
                )))

            async def send_tool_response(self, function_responses):
                await self.queue.put(types.LiveServerMessage(server_content=types.LiveServerContent(
                    output_transcription=types.Transcription(text="I am Hugback, an AI companion."),
                    turn_complete=True,
                )))

            async def receive(self):
                yield await self.queue.get()

        @asynccontextmanager
        async def connect(*, model, config):
            names = [d.name for tool in config.tools for d in tool.function_declarations]
            self.assertIn("propose_call_wellbeing_signal", names)
            self.assertIn("voice-tone note", config.system_instruction.parts[0].text)
            yield Live()

        provider = SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))
        coordinator = SimpleNamespace(
            begin=lambda owner, session: asyncio.sleep(0, result=CallPlan(
                session_id=session, generation=0, consent=False, time_zone="Asia/Kolkata")),
            finish=lambda owner, plan, turns: asyncio.sleep(0, result="skipped"),
            output=lambda owner, plan, **kwargs: asyncio.sleep(0),
        )
        envelope = {
            "type": "authenticate", "userId": "child-one", "demoParent": True,
            "demoRecipientId": self.mumma,
            "demoRecipientRevision": self.recipient(self.mumma)["revision"],
        }
        with (patch.object(settings, "LOCAL_DEMO_ENABLED", True),
              patch.object(settings, "HUGBACK_AUTH_MODE", "development"),
              patch.object(settings, "HUGBACK_WORKFLOW_ENABLED", False),
              patch("app.main.create_genai_client", return_value=provider),
              patch("app.main.get_demo_store", return_value=self.store),
              patch("app.main.get_demo_coordinator", return_value=coordinator),
              TestClient(app, client=("127.0.0.1", 1234)) as client):
            with client.websocket_connect("/ws", headers={"Origin": "http://127.0.0.1:3000"}) as websocket:
                websocket.send_json(envelope)
                ready = websocket.receive_json()
                self.assertEqual(ready["type"], "ready", ready)
                websocket.send_json({"type": "text", "text": "A fictional quiet day."})
                while not websocket.receive_json().get("turnComplete"):
                    pass
                websocket.send_json({"type": "text", "text": "I am still speaking in this fictional second turn."})
                while not websocket.receive_json().get("turnComplete"):
                    pass
            deadline = time.monotonic() + 2
            while self.recipient(self.mumma)["busy"] and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(self.recipient(self.mumma)["wellbeingSignals"], [])
            state = self.store.start_call("child-one", "call-next", self.mumma,
                                          self.recipient(self.mumma)["revision"])
            self.assertIn("lower_energy", tone_context(state))


if __name__ == "__main__":
    unittest.main()
