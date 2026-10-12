"""Actual HTTP/WebSocket -> Planner -> Live tools -> Reconciler -> Critic, mocked I/O."""
import asyncio
import tempfile
import time
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from google.genai import types
from app.config import settings
from app.main import app
from app.demo.service import get_demo_store
from app.demo.store import DemoStore
from app.workflows.contracts import ConversationPlan, CritiqueReport
from app.memory.followups import ObservationBatch
from test_workflow import BASE, FakeFirestore, cloud_store

OWNER = "synthetic-browser-workflow"
HEADERS = {"Origin": "http://127.0.0.1:3000", "X-Hugback-Development-User": OWNER}

class BrokerWorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        for name, value in {
            "LOCAL_DEMO_ENABLED": True, "HUGBACK_DEMO_STORE": "sqlite", "HUGBACK_WORKFLOW_ENABLED": True,
            "LOCAL_DEMO_DB_PATH": Path(temp.name)/"demo.sqlite3", "HUGBACK_AUTH_MODE": "development",
            "HUGBACK_LIVE_VOICE_MODE": "preset", "HUGBACK_VOICE_DB_PATH": Path(temp.name)/"voice.sqlite3",
            "MEMORY_ENABLED": False, "FOLLOWUPS_ENABLED": False, "FIRESTORE_ENABLED": False,
        }.items():
            item = patch.object(settings, name, value); item.start(); self.addCleanup(item.stop)

    def test_all_four_roles_with_actual_broker_and_both_repositories(self):
        for store in (get_demo_store(), cloud_store(FakeFirestore())):
            configurations, claims, roles = [], [], []
            async def structured(provider, instruction, payload, schema, **kwargs):
                if schema is ConversationPlan:
                    roles.append("planner")
                    return ConversationPlan(consider_followup=payload["followup_available"])
                roles.append("critic")
                return CritiqueReport()
            async def extract(extractor, turns, plan):
                roles.append("reconciler")
                user = next((t for t in turns if t.role == "user" and "fever" in t.text), None)
                return ObservationBatch.model_validate({"observations": [{"topic": "fever", "action": "open",
                    "source_turn": user.turn_index, "evidence": "I have fever today."}] if user else []})
            class Live:
                def __init__(self): self.queue = asyncio.Queue()
                async def send_client_content(self, **kwargs):
                    await self.queue.put(types.LiveServerMessage(tool_call=types.LiveServerToolCall(
                        function_calls=[types.FunctionCall(id="f", name="claim_followup", args={})])))
                async def send_tool_response(self, function_responses):
                    claims.append(function_responses[0].response)
                    await self.queue.put(types.LiveServerMessage(server_content=types.LiveServerContent(
                        output_transcription=types.Transcription(text="I am Hugback, an AI companion."), turn_complete=True)))
                async def receive(self): yield await self.queue.get()
            @asynccontextmanager
            async def connect(*, model, config):
                configurations.append(config)
                yield Live()
            provider = SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))
            with (patch("app.main.create_genai_client", return_value=provider),
                  patch("app.main.get_demo_store", return_value=store),
                  patch("app.demo.routes.get_demo_store", return_value=store),
                  patch("app.workflows.provider.GoogleStructuredProvider.generate", new=structured),
                  patch("app.memory.followup_extractor.GoogleFollowupExtractor.extract", new=extract),
                  TestClient(app, client=("127.0.0.1", 2222)) as client):
                family = client.post("/api/demo/family", headers=HEADERS, json=BASE|{"label":"Mother"}).json()
                rid = family["recipients"][0]["recipientId"]
                def call(text):
                    with client.websocket_connect("/ws", headers={"Origin": HEADERS["Origin"]}) as ws:
                        ws.send_json({"type":"authenticate", "userId":OWNER, "demoParent":True,
                            "demoRecipientId":rid, "demoRecipientRevision":0, "simulateWorkflowConsent":True})
                        ready = ws.receive_json(); self.assertEqual(ready["type"], "ready", ready)
                        ws.send_json({"type":"text", "text":text})
                        while not ws.receive_json().get("turnComplete"): pass
                    deadline = time.monotonic()+3
                    while time.monotonic() < deadline:
                        recipient = store.get(OWNER)["recipients"][0]
                        if not recipient["busy"] and recipient["calls"][-1].get("workflow", {}).get("critic") == "completed":
                            return recipient
                        time.sleep(.01)
                    self.fail("Bounded finalization failed: " + str(recipient["calls"]))
                first = call("I have fever today.")
                self.assertEqual(first["memoryCount"], 1)
                self.assertEqual(first["calls"][-1]["workflow"], {"planner":"ready", "reconciler":"processed", "critic":"completed"})
                call("Hello again.")
                self.assertFalse(claims[0]["allowed"]); self.assertTrue(claims[1]["allowed"])
                self.assertEqual(roles.count("planner"), 2)
                self.assertEqual(roles.count("reconciler"), 2)
                self.assertEqual(roles.count("critic"), 2)
                self.assertIn("Validated conversation plan", configurations[0].system_instruction.parts[0].text)
                self.assertNotIn("qualityReports", str(client.get("/api/demo/family", headers=HEADERS).json()))
                self.assertEqual(len(store.inspect_quality(OWNER, rid)), 2)

    def test_workflow_acknowledgement_required_before_any_provider(self):
        with patch("app.main.create_genai_client") as live, patch("app.main.prepare_call", new_callable=AsyncMock) as planner:
            with TestClient(app, client=("127.0.0.1", 2222)) as client:
                family = client.post("/api/demo/family", headers=HEADERS, json=BASE).json()
                with client.websocket_connect("/ws", headers={"Origin": HEADERS["Origin"]}) as ws:
                    ws.send_json({"type":"authenticate", "userId":OWNER, "demoParent":True,
                        "demoRecipientId":family["recipients"][0]["recipientId"], "demoRecipientRevision":0})
                    self.assertIn("Acknowledge", ws.receive_json()["message"])
            live.assert_not_called(); planner.assert_not_called()

if __name__ == "__main__": unittest.main()
