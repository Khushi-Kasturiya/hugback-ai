"""Redacted post-call diagnostics through the real broker. No Google I/O."""
import asyncio
import json
import tempfile
import time
import unittest
from contextlib import asynccontextmanager, ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient
from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.config import settings
from app.demo.store import DemoError, DemoStore
from app.main import app
from app.memory.failures import memory_error_code
from app.memory.followup_extractor import GoogleFollowupExtractor
from app.memory.followup_service import FollowupCoordinator
from app.memory.followups import ObservationBatch
from app.workflows.contracts import ConversationPlan

OWNER = "synthetic-memory-diagnostics"
HEADERS = {"Origin": "http://127.0.0.1:3000", "X-Hugback-Development-User": OWNER}


class MemoryErrorTests(unittest.TestCase):
    def test_error_categories_are_fixed_and_do_not_contain_provider_data(self):
        for code, expected in [(400, "provider_request_rejected"), (401, "provider_access"),
                               (403, "provider_access"), (404, "model_unavailable"),
                               (429, "rate_limited"), (503, "provider_unavailable")]:
            failure = errors.APIError(code, {"error": {"message": "private-token-and-transcript"}})
            self.assertEqual(memory_error_code(failure), expected)
        for failure, expected in [
            (TimeoutError(), "timeout"), (httpx.ReadTimeout("private"), "timeout"),
            (httpx.ConnectError("private"), "network_unavailable"),
            (RuntimeError("private"), "processing_failed"),
        ]:
            self.assertEqual(memory_error_code(failure), expected)
        try:
            ObservationBatch.model_validate({"observations": "private-invalid-output"})
        except ValidationError as exc:
            self.assertEqual(memory_error_code(exc), "invalid_output")

    def run_call(self, *, failure=None, memory=True, coordinator_unavailable=False, workflow=False, extractor=None):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            stack.enter_context(patch.multiple(settings,
                LOCAL_DEMO_ENABLED=True, HUGBACK_DEMO_STORE="sqlite", HUGBACK_WORKFLOW_ENABLED=workflow,
                LOCAL_DEMO_DB_PATH=Path(directory)/"family.sqlite3", HUGBACK_AUTH_MODE="development",
                HUGBACK_LIVE_VOICE_MODE="preset", HUGBACK_VOICE_DB_PATH=Path(directory)/"voice.sqlite3",
                HUGBACK_REPLICATED_TTS_ENABLED=False, MEMORY_ENABLED=False,
                FOLLOWUPS_ENABLED=False, FIRESTORE_ENABLED=False,
            ))
            store = DemoStore(settings.LOCAL_DEMO_DB_PATH)
            batch = ObservationBatch.model_validate({"observations": [{
                "topic": "fever", "action": "open", "source_turn": 0, "evidence": "I have fever today.",
            }]})
            coordinator = FollowupCoordinator(store, extractor or SimpleNamespace(
                extract=AsyncMock(return_value=batch, side_effect=failure)))
            if coordinator_unavailable:
                coordinator = SimpleNamespace(begin=AsyncMock(side_effect=RuntimeError("synthetic")))
            stack.enter_context(patch("app.main.get_demo_coordinator", return_value=coordinator))
            stack.enter_context(patch("app.main.get_demo_store", return_value=store))
            stack.enter_context(patch("app.main.prepare_call", new_callable=AsyncMock,
                                      return_value=(ConversationPlan(), "ready")))
            stack.enter_context(patch("app.main.finish_quality_review", new_callable=AsyncMock))
            checkpoint = store.workflow_checkpoint
            def checkpoint_failure(parent, session, stages, **kwargs):
                if "reconciler" in stages:
                    raise RuntimeError("status unavailable")
                return checkpoint(parent, session, stages, **kwargs)
            if workflow:
                stack.enter_context(patch.object(store, "workflow_checkpoint", side_effect=checkpoint_failure))

            class Live:
                def __init__(self): self.queue = asyncio.Queue()
                async def send_client_content(self, **kwargs):
                    await self.queue.put(types.LiveServerMessage(server_content=types.LiveServerContent(
                        output_transcription=types.Transcription(text="I am Hugback, an AI companion."),
                        turn_complete=True)))
                async def receive(self): yield await self.queue.get()

            @asynccontextmanager
            async def connect(**kwargs): yield Live()
            stack.enter_context(patch("app.main.create_genai_client", return_value=SimpleNamespace(
                aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))))
            client = stack.enter_context(TestClient(app, client=("127.0.0.1", 1234)))
            family = client.post("/api/demo/family", headers=HEADERS, json={
                "syntheticOnly": True, "simulateChildConsent": True,
                "simulateParentConsent": True, "enableMemory": memory,
            }).json()
            rid = family["recipients"][0]["recipientId"]
            with client.websocket_connect("/ws", headers={"Origin": HEADERS["Origin"]}) as ws:
                ws.send_json({"type": "authenticate", "userId": OWNER, "demoParent": True,
                              "demoRecipientId": rid, "demoRecipientRevision": 0,
                              "simulateWorkflowConsent": True})
                self.assertEqual(ws.receive_json()["type"], "ready")
                ws.send_json({"type": "text", "text": "I have fever today."})
                while not ws.receive_json().get("turnComplete"): pass
            deadline = time.monotonic()+3
            while time.monotonic() < deadline:
                recipient = store.get(OWNER)["recipients"][0]
                if not recipient["busy"]:
                    break
                time.sleep(.01)
            self.assertFalse(recipient["busy"])
            with self.assertRaises(DemoError):
                store.call_status(rid, recipient["calls"][-1]["sessionId"], "memory_failed",
                                  memory_error="private arbitrary error")
            return recipient

    def test_actual_extractor_wire_request_commits_memory_through_broker(self):
        requests = []
        def respond(request):
            body = json.loads(request.content)
            requests.append(body)
            generation = body["generationConfig"]
            self.assertNotIn("responseSchema", generation)
            self.assertFalse(generation["responseJsonSchema"]["additionalProperties"])
            return httpx.Response(200, json={"candidates": [{
                "content": {"role": "model", "parts": [{"text": json.dumps({"observations": [{
                    "topic": "fever", "action": "open", "source_turn": 0, "evidence": "I have fever today.",
                }]})}]}, "finishReason": "STOP",
            }]})
        provider = genai.Client(
            api_key="synthetic-offline-key", vertexai=False, http_options={
                "api_version": "v1beta",
                "async_client_args": {"transport": httpx.MockTransport(respond)},
            })
        with patch("app.memory.followup_extractor.genai.Client", return_value=provider):
            state = self.run_call(extractor=GoogleFollowupExtractor(local_demo=True))
        self.assertEqual(len(requests), 1)
        self.assertEqual(state["calls"][-1]["status"], "completed")
        self.assertNotIn("memoryErrorCode", state["calls"][-1])
        self.assertEqual(state["memoryCount"], 1)

    def test_provider_failure_persists_safe_reason_even_when_workflow_is_off(self):
        state = self.run_call(failure=errors.APIError(429, {"error": {"message": "private-body"}}))
        self.assertEqual(state["calls"][-1]["status"], "memory_failed")
        self.assertEqual(state["calls"][-1]["memoryErrorCode"], "rate_limited")
        self.assertEqual(state["memoryCount"], 0)
        self.assertNotIn("private-body", json.dumps(state))
        self.assertNotIn("I have fever", json.dumps(state))

    def test_status_checkpoint_failure_does_not_mislabel_saved_memory(self):
        state = self.run_call(workflow=True)
        self.assertEqual(state["calls"][-1]["status"], "completed")
        self.assertNotIn("memoryErrorCode", state["calls"][-1])
        self.assertEqual(state["memoryCount"], 1)

    def test_unavailable_context_distinguishes_disabled_memory_from_failure(self):
        disabled = self.run_call(memory=False, coordinator_unavailable=True)
        self.assertEqual(disabled["calls"][-1]["status"], "completed")
        self.assertNotIn("memoryErrorCode", disabled["calls"][-1])
        enabled = self.run_call(memory=True, coordinator_unavailable=True)
        self.assertEqual(enabled["calls"][-1]["status"], "memory_failed")
        self.assertEqual(enabled["calls"][-1]["memoryErrorCode"], "context_unavailable")
