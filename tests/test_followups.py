"""Synthetic-only lifecycle, races, privacy and extraction tests; no cloud I/O."""

import asyncio
import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from pydantic import ValidationError
from google import genai
import httpx

from app.agent.live_session import create_live_config
from app.memory.followup_extractor import GoogleFollowupExtractor
from app.memory.followup_service import FollowupCoordinator, get_followup_coordinator
from app.memory.followups import (
    CallPlan, FollowupState, Observation, ObservationBatch, context_card,
)
from app.memory.models import TranscriptTurn
from app.memory.transcript import TranscriptCollector

T0 = datetime(2026, 10, 11, 10, tzinfo=timezone.utc)


class AtomicMemoryStore:
    """Test double with transaction isolation, not a production fallback."""
    def __init__(self):
        self.states = {}
        self.lock = asyncio.Lock()

    async def transact(self, owner, mutate):
        async with self.lock:
            state = self.states.get(owner, FollowupState()).model_copy(deep=True)
            result = mutate(state)
            # Validate the persisted shape after every mutation, like a reload.
            self.states[owner] = FollowupState.model_validate(state.model_dump())
            return result


def turn(text, *, when=T0, index=0, role="user"):
    return TranscriptTurn(role=role, text=text, timestamp=when, turn_index=index)


def observation(action="open", evidence="I have fever today.", *, topic="fever", index=0):
    return Observation(topic=topic, action=action, evidence=evidence, source_turn=index)


class FollowupLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = AtomicMemoryStore()
        self.extractor = SimpleNamespace(extract=AsyncMock(return_value=ObservationBatch()))
        self.service = FollowupCoordinator(self.store, self.extractor)
        await self.service.record_verified_consent(
            "parent-a", version="test-v1", source="synthetic-enrollment",
            time_zone="Asia/Kolkata", now=T0 - timedelta(days=1),
        )

    async def seed_fever(self):
        self.extractor.extract.return_value = ObservationBatch(observations=[observation()])
        plan = await self.service.begin("parent-a", "first-call", now=T0)
        result = await self.service.finish("parent-a", plan, [turn("I have fever today.")], now=T0 + timedelta(minutes=1))
        self.assertEqual(result, "processed")
        return plan

    async def test_fever_next_session_improved_then_resolved(self):
        await self.seed_fever()
        next_day = T0 + timedelta(days=1)
        plan = await self.service.begin("parent-a", "next-call", now=next_day)
        self.assertEqual(plan.selected.topic, "fever")
        result = await self.service.claim("parent-a", plan, now=next_day)
        self.assertTrue(result["allowed"])
        self.assertIn("+05:30", result["reported_at"])
        self.assertIn("last time", result["guidance"])
        self.assertFalse((await self.service.claim("parent-a", plan, now=next_day))["allowed"])

        self.extractor.extract.return_value = ObservationBatch(
            observations=[observation("improved", "A little better.")]
        )
        await self.service.finish(
            "parent-a", plan, [turn("A little better.", when=next_day)],
            now=next_day + timedelta(minutes=1),
        )
        self.assertEqual(self.store.states["parent-a"].concerns["fever"].status, "improved")
        # Another call ten minutes later must not restart the questionnaire.
        soon = await self.service.begin("parent-a", "rapid-reconnect", now=next_day + timedelta(minutes=10))
        self.assertIsNone(soon.selected)
        later = next_day + timedelta(days=1)
        final = await self.service.begin("parent-a", "third-call", now=later)
        self.extractor.extract.return_value = ObservationBatch(
            observations=[observation("resolved", "My fever is completely gone.")]
        )
        await self.service.finish(
            "parent-a", final, [turn("My fever is completely gone.", when=later)],
            now=later + timedelta(minutes=1),
        )
        self.assertEqual(self.store.states["parent-a"].concerns["fever"].status, "resolved")
        self.assertIsNone((await self.service.begin("parent-a", "fourth-call", now=later + timedelta(days=1))).selected)

    async def test_no_answer_and_interruption_do_not_mark_resolved_or_heard(self):
        await self.seed_fever()
        now = T0 + timedelta(days=1)
        plan = await self.service.begin("parent-a", "second", now=now)
        item = self.store.states["parent-a"].concerns["fever"]
        self.assertIsNone(item.last_generated_at)  # planned is not asked
        await self.service.claim("parent-a", plan, now=now)
        await self.service.output("parent-a", plan, now=now + timedelta(seconds=1))
        await self.service.output("parent-a", plan, interrupted=True, now=now + timedelta(seconds=2))
        self.extractor.extract.return_value = ObservationBatch()
        await self.service.finish(
            "parent-a", plan, [turn("Let's talk about cricket.", when=now)], now=now + timedelta(minutes=1)
        )
        item = self.store.states["parent-a"].concerns["fever"]
        self.assertEqual(item.status, "open")
        self.assertIsNotNone(item.last_generated_at)
        self.assertIsNotNone(item.last_interrupted_at)
        self.assertNotIn("heard", item.model_dump())
        self.assertIsNone((await self.service.begin("parent-a", "third", now=now + timedelta(minutes=5))).selected)

    async def test_parent_already_mentions_topic_so_no_followup_is_authorized(self):
        await self.seed_fever()
        now = T0 + timedelta(days=1)
        plan = await self.service.begin("parent-a", "next", now=now)
        result = await self.service.claim(
            "parent-a", plan, latest_user_text="My fever is gone now.", now=now,
        )
        self.assertFalse(result["allowed"])
        self.assertFalse((await self.service.claim("parent-a", plan, latest_user_text="Hello.", now=now))["allowed"])
        self.assertIsNone(self.store.states["parent-a"].concerns["fever"].last_generated_at)

    async def test_atomic_reservation_only_one_concurrent_call_gets_a_topic(self):
        await self.seed_fever()
        plans = await asyncio.gather(*[
            self.service.begin("parent-a", f"parallel-{i}", now=T0 + timedelta(days=1))
            for i in range(10)
        ])
        self.assertEqual(sum(p.selected is not None for p in plans), 1)

    async def test_different_parent_never_receives_or_generates_the_memory(self):
        await self.seed_fever()
        plan = await self.service.begin("parent-b", "another-call", now=T0 + timedelta(days=1))
        self.assertFalse(plan.consent)
        self.assertIsNone(plan.selected)
        self.extractor.extract.reset_mock()
        await self.service.finish("parent-b", plan, [turn("I have fever today.")], now=T0 + timedelta(days=1))
        self.extractor.extract.assert_not_awaited()

    async def test_expiry_removes_context_but_does_not_claim_recovery(self):
        await self.seed_fever()
        plan = await self.service.begin("parent-a", "late-call", now=T0 + timedelta(days=4))
        self.assertIsNone(plan.selected)
        self.assertEqual(self.store.states["parent-a"].concerns, {})
        self.assertNotIn("fever", context_card(plan))

    async def test_suppress_and_forget_remove_evidence_and_block_regeneration(self):
        for action, text in (("suppress", "Don't ask about my fever."), ("forget", "Forget my fever.")):
            with self.subTest(action=action):
                await self.asyncSetUp()
                await self.seed_fever()
                now = T0 + timedelta(days=1)
                plan = await self.service.begin("parent-a", "second", now=now)
                result = await self.service.control("parent-a", plan, action, "fever", text, text)
                self.assertTrue(result["changed"])
                self.assertNotIn("fever", self.store.states["parent-a"].concerns)
                self.assertNotIn("I have fever today", self.store.states["parent-a"].model_dump_json())
                self.assertEqual(
                    await self.service.finish("parent-a", plan, [turn(text, when=now)], now=now), "revoked"
                )
                future = await self.service.begin("parent-a", "new-report", now=now + timedelta(days=2))
                self.extractor.extract.return_value = ObservationBatch(observations=[observation()])
                await self.service.finish(
                    "parent-a", future, [turn("I have fever today.", when=now + timedelta(days=2))],
                    now=now + timedelta(days=2, minutes=1),
                )
                self.assertNotIn("fever", self.store.states["parent-a"].concerns)

    async def test_control_requires_current_user_evidence_and_grounded_target(self):
        await self.seed_fever()
        plan = await self.service.begin("parent-a", "second", now=T0 + timedelta(days=1))
        for action, topic, evidence, current in (
            ("forget", "fever", "Forget my fever.", "Hello."),
            ("forget", "fever", "fever", "I have fever."),
            ("revoke_all", None, "Forget my fever.", "Forget my fever."),
            ("suppress", "sleep", "Don't ask about this.", "Don't ask about this."),
        ):
            result = await self.service.control("parent-a", plan, action, topic, evidence, current)
            self.assertFalse(result["changed"])
        self.assertIn("fever", self.store.states["parent-a"].concerns)

    async def test_hinglish_and_hindi_privacy_controls_use_the_same_topic(self):
        for text in ("Bukhar ke baare mein mat poocho.", "बुखार के बारे में मत पूछो।"):
            with self.subTest(text=text):
                await self.asyncSetUp()
                await self.seed_fever()
                plan = await self.service.begin("parent-a", "next", now=T0 + timedelta(days=1))
                result = await self.service.control("parent-a", plan, "suppress", "fever", text, text)
                self.assertTrue(result["changed"])
                self.assertEqual(self.store.states["parent-a"].blocked_topics, ["fever"])

    async def test_revoke_during_extraction_prevents_resurrection(self):
        plan = await self.service.begin("parent-a", "first", now=T0)
        async def extracting(*args):
            await self.service.delete_all("parent-a")
            return ObservationBatch(observations=[observation()])
        self.extractor.extract.side_effect = extracting
        await self.service.finish("parent-a", plan, [turn("I have fever today.")], now=T0 + timedelta(minutes=1))
        self.assertEqual(self.store.states["parent-a"].concerns, {})
        self.assertFalse(self.store.states["parent-a"].consent)

    async def test_revoke_after_plan_before_claim_does_not_release_private_context(self):
        await self.seed_fever()
        plan = await self.service.begin("parent-a", "next", now=T0 + timedelta(days=1))
        await self.service.delete_all("parent-a")
        self.assertEqual(await self.service.claim("parent-a", plan, now=T0 + timedelta(days=1)), {"allowed": False})
        self.assertNotIn("I have fever", context_card(plan))

    async def test_unhandled_privacy_request_holds_recall_without_upload(self):
        await self.seed_fever()
        now = T0 + timedelta(days=1)
        plan = await self.service.begin("parent-a", "next", now=now)
        self.extractor.extract.reset_mock()
        status = await self.service.finish("parent-a", plan, [turn("Don't remember this.", when=now)], now=now)
        self.assertEqual(status, "privacy_hold")
        self.extractor.extract.assert_not_awaited()
        self.assertIsNone((await self.service.begin("parent-a", "later", now=now + timedelta(days=1))).selected)
        self.assertEqual((await self.service.inspect("parent-a", now=now))["concerns"], [])

    async def test_provenance_rejects_hallucinated_ids_model_text_and_future_dates(self):
        plan = await self.service.begin("parent-a", "first", now=T0)
        self.extractor.extract.return_value = ObservationBatch(observations=[
            observation(index=10),
            observation(index=1),
            observation(index=2),
            observation(evidence="Invented private detail.", index=3),
        ])
        await self.service.finish("parent-a", plan, [
            turn("I have fever today.", index=1, role="model"),
            turn("I have fever today.", index=2, when=T0 + timedelta(days=1)),
            turn("Something unrelated.", index=3),
        ], now=T0)
        self.assertEqual(self.store.states["parent-a"].concerns, {})

    async def test_duplicate_session_and_out_of_order_processing_do_not_reopen(self):
        first = await self.seed_fever()
        prior = self.store.states["parent-a"].model_dump_json()
        prior_requests = self.extractor.extract.await_count
        await self.service.finish("parent-a", first, [turn("I have fever today.")], now=T0 + timedelta(minutes=1))
        self.assertEqual(self.extractor.extract.await_count, prior_requests)
        self.assertEqual(self.store.states["parent-a"].model_dump_json(), prior)
        now = T0 + timedelta(days=1)
        second = await self.service.begin("parent-a", "second", now=now)
        self.extractor.extract.return_value = ObservationBatch(observations=[observation("resolved", "My fever is gone.")])
        await self.service.finish("parent-a", second, [turn("My fever is gone.", when=now)], now=now)
        delayed = await self.service.begin("parent-a", "delayed", now=now)
        self.extractor.extract.return_value = ObservationBatch(observations=[observation()])
        await self.service.finish("parent-a", delayed, [turn("I have fever today.")], now=now)
        self.assertEqual(self.store.states["parent-a"].concerns["fever"].status, "resolved")

    async def test_call_during_processing_gets_pending_not_stale_context(self):
        await self.seed_fever()
        now = T0 + timedelta(days=1)
        next_plan = await self.service.begin("parent-a", "second", now=now)
        inspected = []
        async def extracting(*args):
            inspected.append(await self.service.begin("parent-a", "third", now=now))
            return ObservationBatch()
        self.extractor.extract.side_effect = extracting
        await self.service.finish("parent-a", next_plan, [turn("Hello.", when=now)], now=now)
        self.assertEqual(inspected[0].memory_status, "pending")
        self.assertIsNone(inspected[0].selected)
        self.assertIn("pending", context_card(inspected[0]))
        self.assertEqual(self.store.states["parent-a"].pending_sessions, {})

    async def test_new_report_after_resolution_is_a_new_episode(self):
        await self.seed_fever()
        now = T0 + timedelta(days=1)
        second = await self.service.begin("parent-a", "second", now=now)
        self.extractor.extract.return_value = ObservationBatch(observations=[observation("resolved", "My fever is gone.")])
        await self.service.finish("parent-a", second, [turn("My fever is gone.", when=now)], now=now)
        later = now + timedelta(days=1)
        third = await self.service.begin("parent-a", "third", now=later)
        self.extractor.extract.return_value = ObservationBatch(observations=[observation()])
        await self.service.finish("parent-a", third, [turn("I have fever today.", when=later)], now=later)
        self.assertEqual(self.store.states["parent-a"].concerns["fever"].first_reported_at, later)

    async def test_extraction_failure_does_not_invent_or_save_new_memory(self):
        plan = await self.service.begin("parent-a", "first", now=T0)
        self.extractor.extract.side_effect = RuntimeError("synthetic provider outage")
        with self.assertRaises(RuntimeError):
            await self.service.finish("parent-a", plan, [turn("I have fever today.")], now=T0)
        self.assertEqual(self.store.states["parent-a"].concerns, {})

    async def test_schema_rejects_extra_permissions_and_other_subjects(self):
        for extra in ({"owner": "parent-b"}, {"subject": "child"}, {"retention_days": 365}):
            with self.assertRaises(ValidationError):
                Observation.model_validate({**observation().model_dump(), **extra})


class ExtractorAndConfigTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        enabled = patch("app.config.settings.FOLLOWUPS_ENABLED", True)
        enabled.start()
        self.addCleanup(enabled.stop)

    async def test_google_request_contains_source_time_zone_and_strict_schema(self):
        generate = AsyncMock(return_value=SimpleNamespace(
            text=ObservationBatch(observations=[observation()]).model_dump_json()
        ))
        client = SimpleNamespace(
            aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate), aclose=AsyncMock()),
            close=Mock(),
        )
        plan = CallPlan(session_id="synthetic", generation=1, consent=True, time_zone="Asia/Kolkata")
        with (
            patch("app.memory.followup_extractor.genai.Client", return_value=client) as factory,
            patch("app.config.settings.GEMINI_API_KEY", "synthetic-key"),
        ):
            result = await GoogleFollowupExtractor().extract([turn("I have fever today.")], plan)
        request = generate.call_args.kwargs
        payload = json.loads(request["contents"])
        self.assertEqual(payload["time_zone"], "Asia/Kolkata")
        self.assertEqual(payload["turns"][0]["timestamp"], "2026-10-11T10:00:00Z")
        self.assertEqual(request["config"].response_schema, ObservationBatch)
        self.assertEqual(result.observations[0].topic, "fever")
        self.assertFalse(factory.call_args.kwargs["vertexai"])
        client.aio.aclose.assert_awaited_once()
        client.close.assert_called_once()

    async def test_oversized_input_rejected_without_provider(self):
        with patch("app.memory.followup_extractor.genai.Client") as factory:
            with self.assertRaises(ValueError):
                await GoogleFollowupExtractor().extract(
                    [turn("x" * 60_001)], CallPlan(session_id="s", generation=0, consent=True, time_zone="UTC")
                )
            factory.assert_not_called()

    async def test_invalid_model_json_does_not_become_memory(self):
        client = SimpleNamespace(
            aio=SimpleNamespace(
                models=SimpleNamespace(generate_content=AsyncMock(return_value=SimpleNamespace(text="not json"))),
                aclose=AsyncMock(),
            ), close=Mock(),
        )
        with patch("app.memory.followup_extractor.genai.Client", return_value=client):
            with self.assertRaises(ValidationError):
                await GoogleFollowupExtractor().extract(
                    [turn("Hello.")], CallPlan(session_id="s", generation=0, consent=True, time_zone="UTC")
                )
        client.aio.aclose.assert_awaited_once()

    async def test_actual_sdk_structured_request_serializes_without_network(self):
        requests = []
        def respond(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={
                "candidates": [{
                    "content": {"role": "model", "parts": [{
                        "text": ObservationBatch(observations=[observation()]).model_dump_json()
                    }]},
                    "finishReason": "STOP",
                }]
            })
        client = genai.Client(
            api_key="synthetic-offline-key", vertexai=False,
            http_options={
                "api_version": "v1beta",
                "async_client_args": {"transport": httpx.MockTransport(respond)},
            },
        )
        with patch("app.memory.followup_extractor.genai.Client", return_value=client):
            result = await GoogleFollowupExtractor().extract(
                [turn("I have fever today.")],
                CallPlan(session_id="s", generation=1, consent=True, time_zone="Asia/Kolkata"),
            )
        self.assertEqual(len(requests), 1)
        generation = requests[0]["generationConfig"]
        self.assertEqual(generation["responseMimeType"], "application/json")
        self.assertIn("responseSchema", generation)
        self.assertEqual(result.observations[0].topic, "fever")

    async def test_disabled_feature_does_not_construct_firestore_or_extractor(self):
        with patch("app.config.settings.FOLLOWUPS_ENABLED", False):
            self.assertIsNone(get_followup_coordinator())

    async def test_deletion_cannot_claim_success_when_storage_is_disabled(self):
        with (
            patch("app.config.settings.FOLLOWUPS_ENABLED", False),
            patch("app.config.settings.FIRESTORE_ENABLED", False),
            self.assertRaises(RuntimeError),
        ):
            get_followup_coordinator(privacy_operation=True)

    async def test_disabled_extractor_never_constructs_provider_client(self):
        with (
            patch("app.config.settings.FOLLOWUPS_ENABLED", False),
            patch("app.memory.followup_extractor.genai.Client") as factory,
            self.assertRaises(ValueError),
        ):
            await GoogleFollowupExtractor().extract(
                [turn("Hello.")], CallPlan(session_id="s", generation=0, consent=True, time_zone="UTC")
            )
        factory.assert_not_called()
    async def test_live_tools_cannot_grant_consent_or_choose_owner(self):
        with patch("app.config.settings.HUGBACK_LIVE_VOICE_MODE", "preset"):
            config = create_live_config(enable_followup_tools=True)
        declarations = config.tools[0].function_declarations
        self.assertEqual([d.name for d in declarations], ["claim_followup", "control_followup"])
        for declaration in declarations:
            self.assertNotIn("user_id", declaration.parameters_json_schema["properties"])
            self.assertNotIn("consent", declaration.parameters_json_schema["properties"])

    async def test_transcript_timestamp_is_observation_time_not_late_flush_time(self):
        collector = TranscriptCollector()
        with patch("app.memory.transcript.datetime") as clock:
            clock.now.return_value = T0
            collector.add_user("I have fever today.")
            clock.now.return_value = T0 + timedelta(days=1)
            self.assertEqual(collector.latest_user_text(), "I have fever today.")
            result = collector.finalize()
        self.assertEqual(result[0].timestamp, T0)
