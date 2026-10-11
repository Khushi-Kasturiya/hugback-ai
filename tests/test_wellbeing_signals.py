"""Consent, isolation and abstention tests for local-demo call signals."""

import asyncio
import json
import tempfile
import time
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from google.genai import types

from app.agent.live_session import create_live_config
from app.config import settings
from app.demo.models import CreateFamily, CreateRecipient, SetWellbeingSharing
from app.demo.store import DemoStore
from app.memory.models import TranscriptTurn
from app.memory.followups import CallPlan
from app.wellbeing.models import WellbeingSignalDraft
from app.wellbeing.service import SignalCollector, contains_signal_privacy_request
from app.main import app


BASE = {
    "syntheticOnly": True,
    "simulateChildConsent": True,
    "simulateParentConsent": True,
    "enableMemory": False,
}


class WellbeingSignalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = DemoStore(Path(temp.name) / "demo.sqlite3")
        for name, value in {
            "LOCAL_DEMO_DB_PATH": self.store.path,
            "LOCAL_DEMO_ENABLED": True,
            "HUGBACK_AUTH_MODE": "development",
            "HUGBACK_LIVE_VOICE_MODE": "preset",
        }.items():
            patcher = patch.object(settings, name, value)
            patcher.start(); self.addCleanup(patcher.stop)
        family = self.store.create("child-alpha", CreateFamily(
            **(BASE | {"enableMemory": True}), label="Mother", relationship="mother", enableWellbeingSharing=True,
        ))
        family = self.store.add_recipient("child-alpha", CreateRecipient(
            **BASE, label="Father", relationship="father", enableWellbeingSharing=False,
        ))
        self.mother, self.father = [item["recipientId"] for item in family["recipients"]]

    def recipient(self, recipient_id):
        return next(item for item in self.store.get("child-alpha")["recipients"] if item["recipientId"] == recipient_id)

    def test_signal_requires_consent_active_call_generation_and_is_idempotent(self):
        mother = self.recipient(self.mother)
        internal = self.store.start_call("child-alpha", "call-one", self.mother, mother["revision"])
        draft = WellbeingSignalDraft(category="lower_energy", confidence="medium", basis=["vocal_cues"])
        self.assertFalse(self.store.record_wellbeing_signal(
            self.father, "call-one", 0, draft, model="synthetic-model",
        ))
        self.assertTrue(self.store.record_wellbeing_signal(
            self.mother, "call-one", internal["wellbeingSharing"]["generation"], draft,
            model="synthetic-model",
        ))
        self.assertFalse(self.store.record_wellbeing_signal(
            self.mother, "call-one", internal["wellbeingSharing"]["generation"], draft,
            model="synthetic-model",
        ))
        public = self.recipient(self.mother)
        self.assertEqual(public["wellbeingSignals"][0]["category"], "lower_energy")
        self.assertEqual(public["wellbeingSignals"][0]["displayText"], "Sounded lower-energy during this check-in.")
        self.assertNotIn("transcript", json.dumps(public["wellbeingSignals"]).lower())
        self.assertNotIn("sessionId", public["wellbeingSignals"][0])
        self.assertNotIn("modelVersion", public["wellbeingSignals"][0])
        self.assertEqual(self.recipient(self.father)["wellbeingSignals"], [])

    def test_low_confidence_unclear_and_no_user_speech_are_abstentions(self):
        turns = [TranscriptTurn(role="user", turn_index=0, text="A synthetic hello.")]
        collector = SignalCollector(enabled=True)
        self.assertTrue(collector.propose({
            "category": "upbeat", "confidence": "low", "basis": ["vocal_cues"],
        })["accepted"])
        self.assertIsNone(collector.publishable(turns))
        collector.propose({"category": "unclear", "confidence": "high", "basis": ["conversation_content"]})
        self.assertIsNone(collector.publishable(turns))
        collector.propose({"category": "calm", "confidence": "medium", "basis": ["vocal_cues"]})
        self.assertIsNone(collector.publishable([]))

    def test_parent_dont_share_request_revokes_only_signal_sharing(self):
        mother = self.recipient(self.mother)
        internal = self.store.start_call("child-alpha", "call-private", self.mother, mother["revision"])
        turns = [TranscriptTurn(role="user", turn_index=0, text="Please don't share how I am feeling.")]
        self.assertTrue(contains_signal_privacy_request(turns))
        self.assertTrue(self.store.revoke_wellbeing_sharing(
            self.mother, internal["wellbeingSharing"]["generation"],
        ))
        public = self.recipient(self.mother)
        self.assertFalse(public["wellbeingSharingEnabled"])
        self.assertTrue(public["memoryEnabled"])
        self.assertEqual(public["wellbeingSignals"], [])
        for phrase in (
            "Meri baat meri beti ko mat batana.",
            "मेरी बात बच्चे को मत बताना।",
        ):
            self.assertTrue(contains_signal_privacy_request([
                TranscriptTurn(role="user", turn_index=0, text=phrase),
            ]))

    def test_live_tool_exists_only_when_separate_sharing_is_enabled(self):
        disabled = create_live_config(enable_wellbeing_signal_tool=False)
        self.assertFalse(disabled.tools)
        enabled = create_live_config(
            wellbeing_signal_context="Synthetic signal policy",
            enable_wellbeing_signal_tool=True,
        )
        names = [declaration.name for tool in enabled.tools for declaration in tool.function_declarations]
        self.assertEqual(names, ["propose_call_wellbeing_signal"])
        self.assertIn("Synthetic signal policy", enabled.system_instruction.parts[0].text)

    def test_existing_recipient_requires_fresh_dual_simulation_to_enable(self):
        father = self.recipient(self.father)
        with self.assertRaises(ValueError):
            SetWellbeingSharing(
                syntheticOnly=True, recipientId=self.father, revision=father["revision"],
                enabled=True, simulateChildConsent=True, simulateParentConsent=False,
            )
        updated = self.store.set_wellbeing_sharing("child-alpha", SetWellbeingSharing(
            syntheticOnly=True, recipientId=self.father, revision=father["revision"],
            enabled=True, simulateChildConsent=True, simulateParentConsent=True,
        ))
        father = next(item for item in updated["recipients"] if item["recipientId"] == self.father)
        self.assertTrue(father["wellbeingSharingEnabled"])
        self.assertEqual(father["revision"], 1)

    def test_mock_live_proposal_is_committed_after_call_and_visible_to_child(self):
        tool_result, lifecycle, commits = [], [], []

        class Live:
            def __init__(self):
                self.queue = asyncio.Queue()

            async def send_client_content(self, **kwargs):
                await self.queue.put(types.LiveServerMessage(tool_call=types.LiveServerToolCall(
                    function_calls=[types.FunctionCall(
                        id="signal", name="propose_call_wellbeing_signal",
                        args={"category": "upbeat", "confidence": "high",
                              "basis": ["conversation_content", "vocal_cues"]},
                    )],
                )))

            async def send_tool_response(self, function_responses):
                tool_result.append(function_responses[0].response)
                await self.queue.put(types.LiveServerMessage(server_content=types.LiveServerContent(
                    output_transcription=types.Transcription(text="I am Hugback, an AI companion."),
                    turn_complete=True,
                )))

            async def receive(self):
                yield await self.queue.get()

        @asynccontextmanager
        async def connect(*, model, config):
            names = [declaration.name for tool in config.tools for declaration in tool.function_declarations]
            self.assertIn("propose_call_wellbeing_signal", names)
            self.assertIn("claim_followup", names)
            yield Live()

        provider = SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))
        async def begin(owner, session):
            lifecycle.append("begin")
            return CallPlan(session_id=session, generation=0, consent=False, time_zone="Asia/Kolkata")

        async def finish(owner, plan, turns):
            lifecycle.append(("finish", [turn.text for turn in turns]))
            return "skipped"

        original_record = DemoStore.record_wellbeing_signal
        def record(store, *args, **kwargs):
            commits.append((args, kwargs))
            return original_record(store, *args, **kwargs)

        coordinator = SimpleNamespace(begin=begin, finish=finish)
        mother = self.recipient(self.mother)
        envelope = {
            "type": "authenticate", "userId": "child-alpha", "demoParent": True,
            "demoRecipientId": self.mother, "demoRecipientRevision": mother["revision"],
        }
        with (
            patch("app.main.create_genai_client", return_value=provider),
            patch("app.main.get_demo_coordinator", return_value=coordinator),
            patch.object(DemoStore, "record_wellbeing_signal", new=record),
            TestClient(app, client=("127.0.0.1", 1234)) as client,
        ):
            with client.websocket_connect("/ws", headers={"Origin": "http://127.0.0.1:3000"}) as websocket:
                websocket.send_json(envelope)
                self.assertEqual(websocket.receive_json()["type"], "ready")
                websocket.send_json({"type": "text", "text": "I had a lovely fictional day."})
                while not websocket.receive_json().get("turnComplete"):
                    pass
            self.assertTrue(tool_result[0]["accepted"])
            deadline = time.monotonic() + 2
            signals = self.recipient(self.mother)["wellbeingSignals"]
            while not signals and time.monotonic() < deadline:
                time.sleep(0.01)
                signals = self.recipient(self.mother)["wellbeingSignals"]
        self.assertEqual(len(signals), 1, {"recipient": self.recipient(self.mother), "lifecycle": lifecycle, "commits": commits})
        self.assertEqual(signals[0]["category"], "upbeat")


if __name__ == "__main__":
    unittest.main()
