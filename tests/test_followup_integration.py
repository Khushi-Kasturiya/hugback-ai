"""Broker/adapter contract tests with synthetic content and fake providers."""

import asyncio
import copy
import threading
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from google.genai import types

from app.main import app
from app.memory.followup_store import FirestoreFollowupStore
from app.memory.followups import CallPlan


class FollowupBrokerTests(unittest.TestCase):
    def setUp(self):
        for item in (
            patch("app.main.settings.FOLLOWUPS_ENABLED", True),
            patch("app.main.settings.ELARA_AUTH_MODE", "development"),
            patch("app.main.settings.ELARA_LIVE_VOICE_MODE", "preset"),
        ):
            item.start()
            self.addCleanup(item.stop)

    def test_live_claim_routes_to_authenticated_owner_and_does_not_save_raw_transcript(self):
        finalized = threading.Event()
        plans = []
        configurations = []
        results = []

        async def begin(owner, session):
            plan = CallPlan(session_id=session, generation=1, consent=True, time_zone="Asia/Kolkata")
            plans.append(plan)
            return plan

        async def finish(owner, plan, turns):
            results.append((owner, turns))
            finalized.set()

        coordinator = SimpleNamespace(
            begin=AsyncMock(side_effect=begin), finish=AsyncMock(side_effect=finish),
            claim=AsyncMock(return_value={"allowed": False}),
            output=AsyncMock(),
        )

        class FakeSession:
            def __init__(self):
                self.queue = asyncio.Queue()

            async def send_client_content(self, **kwargs):
                await self.queue.put(types.LiveServerMessage(tool_call=types.LiveServerToolCall(
                    function_calls=[types.FunctionCall(id="f1", name="claim_followup", args={})]
                )))

            async def send_tool_response(self, function_responses):
                self.result = function_responses[0].response
                await self.queue.put(types.LiveServerMessage(server_content=types.LiveServerContent(
                    output_transcription=types.Transcription(text="Hello, I am Elara, an AI companion."),
                    turn_complete=True,
                )))

            async def receive(self):
                yield await self.queue.get()

        @asynccontextmanager
        async def connect(*, model, config):
            configurations.append(config)
            yield FakeSession()

        provider = SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))
        with (
            patch("app.main.get_followup_coordinator", return_value=coordinator),
            patch("app.main.get_memory_service", side_effect=AssertionError("Legacy recall forbidden")) as legacy,
            patch("app.main.get_session_store", side_effect=AssertionError("Raw transcript storage forbidden")) as raw,
            patch("app.main.create_genai_client", return_value=provider),
            TestClient(app) as client,
        ):
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "authenticate", "userId": "parent-12345678"})
                self.assertEqual(ws.receive_json()["type"], "ready")
                ws.send_json({"type": "text", "text": "Hello."})
                self.assertIn("outputTranscription", ws.receive_json())
                self.assertTrue(ws.receive_json()["turnComplete"])
            self.assertTrue(finalized.wait(2))
        self.assertEqual(results[0][0], "parent-12345678")
        self.assertEqual(results[0][1][0].text, "Hello.")
        coordinator.claim.assert_awaited_once_with(
            "parent-12345678", plans[0], latest_user_text="Hello."
        )
        legacy.assert_not_called()
        raw.assert_not_called()
        prompt = configurations[0].system_instruction.parts[0].text
        self.assertIn("Follow-up policy", prompt)
        names = [d.name for t in configurations[0].tools for d in t.function_declarations]
        self.assertEqual(names, ["claim_followup", "control_followup"])

    def test_unavailable_storage_keeps_call_but_never_falls_back_to_old_memory(self):
        configs = []
        class FakeSession:
            async def receive(self):
                await asyncio.Event().wait()
                yield None

        @asynccontextmanager
        async def connect(*, model, config):
            configs.append(config)
            yield FakeSession()

        with (
            patch("app.main.get_followup_coordinator", side_effect=RuntimeError("offline")),
            patch("app.main.get_memory_service", side_effect=AssertionError("No legacy fallback")) as old,
            patch("app.main.get_session_store", side_effect=AssertionError("No raw fallback")) as raw,
            patch("app.main.create_genai_client", return_value=SimpleNamespace(
                aio=SimpleNamespace(live=SimpleNamespace(connect=connect))
            )),
            TestClient(app) as client,
        ):
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "authenticate", "userId": "parent-12345678"})
                self.assertEqual(ws.receive_json()["type"], "ready")
        self.assertIsNone(configs[0].tools)
        self.assertIn("memory is unavailable", configs[0].system_instruction.parts[0].text)
        old.assert_not_called()
        raw.assert_not_called()

    def test_combined_audio_transcript_and_privacy_tool_uses_current_utterance(self):
        words = "Forget my fever."
        plan = CallPlan(session_id="synthetic-call", generation=1, consent=True, time_zone="UTC")
        coordinator = SimpleNamespace(
            begin=AsyncMock(return_value=plan), finish=AsyncMock(),
            control=AsyncMock(return_value={"changed": True}), output=AsyncMock(),
        )

        class FakeSession:
            def __init__(self):
                self.queue = asyncio.Queue()

            async def send_realtime_input(self, **kwargs):
                await self.queue.put(types.LiveServerMessage(
                    server_content=types.LiveServerContent(
                        input_transcription=types.Transcription(text=words),
                    ),
                    tool_call=types.LiveServerToolCall(function_calls=[
                        types.FunctionCall(id="control-1", name="control_followup", args={
                            "action": "forget", "topic": "fever", "evidence": words,
                        })
                    ]),
                ))

            async def send_tool_response(self, **kwargs):
                await self.queue.put(types.LiveServerMessage(
                    server_content=types.LiveServerContent(turn_complete=True)
                ))

            async def receive(self):
                yield await self.queue.get()

        @asynccontextmanager
        async def connect(**kwargs):
            yield FakeSession()

        with (
            patch("app.main.get_followup_coordinator", return_value=coordinator),
            patch("app.main.create_genai_client", return_value=SimpleNamespace(
                aio=SimpleNamespace(live=SimpleNamespace(connect=connect))
            )),
            TestClient(app) as client,
        ):
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "authenticate", "userId": "parent-12345678"})
                self.assertEqual(ws.receive_json()["type"], "ready")
                ws.send_bytes(b"\0\0" * 160)
                self.assertEqual(ws.receive_json()["inputTranscription"]["text"], words)
                self.assertTrue(ws.receive_json()["turnComplete"])
        coordinator.control.assert_awaited_once_with(
            "parent-12345678", plan, "forget", "fever", words, words,
        )

    def test_deletion_tombstones_before_purging_other_stores(self):
        order = []
        async def delete_followups(owner):
            order.append(("tombstone", owner))
        async def delete_semantic(owner):
            order.append(("semantic", owner))
        async def delete_sessions(owner):
            order.append(("sessions", owner))
        with (
            patch("app.main.get_followup_coordinator", return_value=SimpleNamespace(
                delete_all=AsyncMock(side_effect=delete_followups)
            )),
            patch("app.main.get_memory_service", return_value=SimpleNamespace(
                delete_all=AsyncMock(side_effect=delete_semantic)
            )),
            patch("app.main.get_session_store", return_value=SimpleNamespace(
                delete_user_data=AsyncMock(side_effect=delete_sessions)
            )),
            TestClient(app) as client,
        ):
            response = client.delete("/api/memories", headers={"X-Elara-Development-User": "parent-12345678"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([step for step, _ in order], ["tombstone", "semantic", "sessions"])


class FirestoreAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_owner_path_single_document_atomic_write_and_read_only_no_write(self):
        # Exercises our adapter contract, not an emulator/live Firestore claim.
        paths, writes = [], []
        persisted = {}

        class Ref:
            def collection(self, name):
                paths.append(("collection", name))
                return self

            def document(self, name):
                paths.append(("document", name))
                return self

            async def get(self, *, transaction):
                return SimpleNamespace(to_dict=lambda: copy.deepcopy(persisted))

        class Transaction:
            def set(self, ref, data):
                writes.append(data)
                persisted.update(copy.deepcopy(data))

        store = object.__new__(FirestoreFollowupStore)
        store._client = Ref()
        store._client.transaction = Transaction
        store._firestore = SimpleNamespace(async_transactional=lambda fn: fn)
        await store.transact("parent-a", lambda state: setattr(state, "generation", 1))
        self.assertEqual(paths, [
            ("collection", "users"), ("document", "parent-a"),
            ("collection", "private_memory"), ("document", "followups"),
        ])
        self.assertEqual(len(writes), 1)
        self.assertEqual(await store.transact("parent-a", lambda state: state.generation), 1)
        self.assertEqual(len(writes), 1)
        with self.assertRaises(ValueError):
            await store.transact("../parent-b", lambda state: None)
