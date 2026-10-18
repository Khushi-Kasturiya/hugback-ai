"""Offline evaluation of the actual workflow roles, policies and store contracts."""
import asyncio
import copy
import os
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.config import Settings, settings
from app.demo.models import CreateFamily, CreateRecipient, SetTranscriptSharing
from app.demo.repository import FirestoreFamilyRepository
from app.demo.service import require_demo_identity
from app.demo.store import DemoStore, DemoError
from app.auth import UserIdentity
from app.memory.followups import CallPlan, ObservationBatch, revoke
from app.memory.followup_service import FollowupCoordinator
from app.memory.models import TranscriptTurn
from app.workflows.contracts import ConversationPlan, CritiqueReport
from app.workflows.planner import ConversationPlanner, prepare_call, validate_plan, planner_payload, plan_context
from app.workflows.critic import QualityCritic, review_call
from app.voice.profiles import voice_owner

BASE = dict(syntheticOnly=True, simulateChildConsent=True, simulateParentConsent=True, enableMemory=True)

class FakeFirestore:
    """Atomic, rollback-capable double. Not an emulator or IAM verification."""
    def __init__(self):
        self.data = {}
        self.lock = threading.Lock()
        self.abort_once = False
        self.batch_reads = []
    def collection(self, name):
        db = self
        class Collection:
            def document(self, key):
                path = name + "/" + key
                class Ref:
                    def get(self, *, transaction):
                        if transaction.writes:
                            raise AssertionError("Firestore reads must precede writes")
                        return SimpleNamespace(to_dict=lambda: copy.deepcopy(db.data.get(path)))
                ref = Ref(); ref.path = path; ref.id = key
                return ref
        return Collection()
    def get_all(self, refs, *, transaction):
        self.batch_reads.append([ref.path for ref in refs])
        # BatchGet does not promise request order.
        for ref in reversed(refs):
            snapshot = ref.get(transaction=transaction)
            yield SimpleNamespace(reference=ref, to_dict=snapshot.to_dict)
    def transaction(self, **kwargs):
        return SimpleNamespace(writes=[], set=lambda ref, value: None)
    def transactional(self, fn):
        def run(tx):
            with self.lock:
                while True:
                    tx.writes = []
                    tx.set = lambda ref, value: tx.writes.append((ref.path, copy.deepcopy(value)))
                    result = fn(tx)
                    if self.abort_once:
                        self.abort_once = False
                        continue
                    self.data.update(tx.writes)
                    return result
        return run

def cloud_store(db):
    repo = FirestoreFamilyRepository("demo-offline", "hugback-synthetic", client=db)
    repo.firestore = SimpleNamespace(transactional=db.transactional, SERVER_TIMESTAMP="server-timestamp")
    return DemoStore(repository=repo)

class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_isolated_firestore_test_store_keeps_consented_history_recipient_scoped(self):
        db = FakeFirestore()
        store = cloud_store(db)
        family = store.create("synthetic-owner", CreateFamily(**BASE, label="Mother"))
        recipient = family["recipients"][0]["recipientId"]
        store.set_transcript_sharing("synthetic-owner", SetTranscriptSharing(
            syntheticOnly=True, recipientId=recipient, revision=0, enabled=True,
            simulateChildConsent=True, simulateParentConsent=True))
        store.start_call("synthetic-owner", "session-test", recipient, 1)
        self.assertTrue(store.record_transcript(recipient, "session-test", 1, [
            TranscriptTurn(role="user", turn_index=0, text="Fictional hello.")]))
        self.assertTrue(store.record_call_summary(
            recipient, "session-test", 1, "A fictional greeting was recorded for this call."))
        store.call_status(recipient, "session-test", "completed", release=True)
        restored = cloud_store(db)
        self.assertIn("fictional greeting", restored.get_call_summary(
            "synthetic-owner", recipient, "session-test")["summary"])
        self.assertNotIn("transcript", restored.get("synthetic-owner")["recipients"][0]["calls"][0])
        self.assertFalse(any("Fictional hello." in str(value) for key, value in db.data.items() if "recipients/" in key))

    async def test_planner_only_references_authorized_background(self):
        state = {"language": "hi-en", "background": [
            {"role": "parent", "timestamp": "2026-10-01", "text": "I like my fictional garden."}]}
        provider = SimpleNamespace(generate=AsyncMock(return_value=ConversationPlan(
            language="hi-en", background_refs=[0])))
        planner = ConversationPlanner(provider)
        result, status = await prepare_call(state, None, planner=planner)
        self.assertEqual(status, "ready")
        self.assertIn("claim_followup", plan_context(result))
        payload = provider.generate.call_args.args[1]
        self.assertNotIn("recipientId", payload)
        for value in [ConversationPlan(background_refs=[9]), ConversationPlan(consider_followup=True)]:
            with self.assertRaises(ValueError): validate_plan(value, planner_payload(state, None))
        with self.assertRaises(ValueError):
            ConversationPlan(language="hi-en", background_refs=[0, 0])

    async def test_planner_timeout_or_invalid_plan_uses_safe_fallback(self):
        state = {"background": []}
        for value in (ValueError("synthetic"), asyncio.TimeoutError()):
            planner = SimpleNamespace(prepare=AsyncMock(side_effect=value))
            plan, status = await prepare_call(state, None, planner=planner)
            self.assertIsNone(plan); self.assertEqual(status, "fallback")
            self.assertEqual(plan_context(plan), "")

    async def test_critic_requires_exact_assistant_evidence_and_honors_privacy(self):
        turns = [TranscriptTurn(role="model", text="I am your real child.", turn_index=1)]
        report = CritiqueReport.model_validate({"findings": [{
            "code": "impersonation", "severity": "error", "source_turn": 1,
            "evidence": "your real child"}]})
        provider = SimpleNamespace(generate=AsyncMock(return_value=report))
        critic = QualityCritic(provider)
        result, status = await review_call(turns, [], background=[], language="en", critic=critic)
        self.assertEqual(status, "completed"); self.assertEqual(len(result.findings), 1)
        report.findings[0].evidence = "not spoken"
        self.assertEqual((await review_call(turns, [], background=[], language="en", critic=critic))[1], "failed")
        provider.generate.reset_mock()
        for text in ["Don't remember this", "Don't share this", "मेरी बात मत बताना"]:
            result, status = await review_call(turns + [TranscriptTurn(role="user", text=text, turn_index=2)],
                [], background=[], language="en", critic=critic)
            self.assertEqual(status, "privacy_skipped")
        provider.generate.assert_not_called()

    async def test_reconciler_continuity_and_isolation_on_both_repositories(self):
        with tempfile.TemporaryDirectory() as directory:
            for store in (DemoStore(Path(directory)/"family.sqlite3"), cloud_store(FakeFirestore())):
                with self.subTest(repository=type(store.repository).__name__):
                    family = store.create("operator-alpha", CreateFamily(**BASE, label="Mother"))
                    family = store.add_recipient("operator-alpha", CreateRecipient(**BASE, label="Father"))
                    mother, father = [r["recipientId"] for r in family["recipients"]]
                    clock = datetime.now(timezone.utc) + timedelta(seconds=1)
                    batch = ObservationBatch.model_validate({"observations": [{"topic": "fever", "action": "open",
                        "source_turn": 0, "evidence": "I have fever today."}]})
                    extractor = SimpleNamespace(extract=AsyncMock(return_value=batch))
                    coordinator = FollowupCoordinator(store, extractor)
                    first = await coordinator.begin(mother, "first", now=clock)
                    turns = [TranscriptTurn(role="user", text="I have fever today.", turn_index=0, timestamp=clock)]
                    await coordinator.finish(mother, first, turns, now=clock+timedelta(seconds=1))
                    second = await coordinator.begin(mother, "second", now=clock+timedelta(seconds=2))
                    self.assertEqual(second.selected.topic, "fever")
                    self.assertTrue((await coordinator.claim(mother, second, now=clock+timedelta(seconds=2)))["allowed"])
                    self.assertFalse((await coordinator.claim(mother, second, now=clock+timedelta(seconds=3)))["allowed"])
                    self.assertIsNone((await coordinator.begin(father, "father-call", now=clock)).selected)
                    batch.observations[0].action = "resolved"
                    batch.observations[0].evidence = "My fever is gone."
                    turns = [TranscriptTurn(role="user", text="My fever is gone.", turn_index=0,
                                            timestamp=clock+timedelta(seconds=4))]
                    await coordinator.finish(mother, second, turns, now=clock+timedelta(seconds=5))
                    self.assertIsNone((await coordinator.begin(mother, "third", now=clock+timedelta(hours=25))).selected)
                    await store.transact(mother, revoke)
                    self.assertEqual(await coordinator.finish(mother, first, turns), "revoked")
                    with self.assertRaises(DemoError): store.start_call("operator-other", "bad", mother, 0)

    async def test_cloud_transaction_retry_rollback_restart_and_stale_revisions(self):
        db = FakeFirestore(); db.abort_once = True
        store = cloud_store(db)
        family = store.create("operator-alpha", CreateFamily(**BASE))
        recipient = family["recipients"][0]
        restarted = cloud_store(db)
        self.assertEqual(restarted.get("operator-alpha")["familyId"], family["familyId"])
        self.assertEqual(len(db.data), 2)  # Retried creation did not leak an index.
        with self.assertRaises(DemoError): restarted.start_call("operator-alpha", "bad", recipient["recipientId"], 20)
        before = copy.deepcopy(db.data)
        def failure(state):
            state["recipients"].clear()
            raise ValueError("synthetic failure")
        with self.assertRaises(ValueError): restarted._run(failure, uid="operator-alpha")
        self.assertEqual(db.data, before)
        # Concurrent starts cannot both get a lease.
        results = []
        def start(session):
            try: store.start_call("operator-alpha", session, recipient["recipientId"], 0); results.append(True)
            except DemoError: results.append(False)
        threads = [threading.Thread(target=start, args=(str(i),)) for i in range(2)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(sorted(results), [False, True])

    async def test_firestore_recipient_transaction_does_not_rewrite_family_or_sibling(self):
        db = FakeFirestore()
        store = cloud_store(db)
        family = store.create("operator-alpha", CreateFamily(**BASE, label="Mother"))
        family = store.add_recipient("operator-alpha", CreateRecipient(**BASE, label="Father"))
        mother, father = [item["recipientId"] for item in family["recipients"]]
        owner = DemoStore.owner("operator-alpha")
        family_path = f"hugback_synthetic_test_families/{owner}"
        father_path = f"hugback_synthetic_test_recipients/{father}"
        family_before = copy.deepcopy(db.data[family_path])
        father_before = copy.deepcopy(db.data[father_path])

        await store.transact(mother, lambda memory: memory.blocked_topics.append("sleep"))

        self.assertEqual(db.data[family_path], family_before)
        self.assertEqual(db.data[father_path], father_before)
        self.assertIn("sleep", db.data[f"hugback_synthetic_test_recipients/{mother}"]["state"]["memory"]["blocked_topics"])

    async def test_legacy_firestore_aggregate_normalizes_on_next_owner_mutation(self):
        db = FakeFirestore()
        store = cloud_store(db)
        family = store.create("operator-alpha", CreateFamily(**BASE, label="Mother"))
        mother = family["recipients"][0]["recipientId"]
        owner = DemoStore.owner("operator-alpha")
        family_path = f"hugback_synthetic_test_families/{owner}"
        mother_path = f"hugback_synthetic_test_recipients/{mother}"
        normalized_family = db.data[family_path]
        mother_state = db.data[mother_path]["state"]
        db.data[family_path] = {
            "syntheticOnly": True, "owner": owner,
            "state": normalized_family["state"] | {"recipients": [mother_state]},
            "expiresAt": normalized_family["expiresAt"],
        }
        db.data[mother_path] = {"owner": owner, "syntheticOnly": True}

        store.add_recipient("operator-alpha", CreateRecipient(**BASE, label="Father"))

        self.assertNotIn("recipients", db.data[family_path]["state"])
        self.assertEqual(len(db.data[family_path]["recipientIds"]), 2)
        self.assertEqual(db.data[mother_path]["state"]["recipientId"], mother)

    async def test_quality_private_bounded_and_stale_writes_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DemoStore(Path(directory)/"family.sqlite3")
            family = store.create("operator-alpha", CreateFamily(**BASE))
            rid = family["recipients"][0]["recipientId"]
            state = store.start_call("operator-alpha", "call", rid, 0)
            report = CritiqueReport.model_validate({"findings": [{"code": "impersonation", "severity": "error",
                "source_turn": 2, "evidence": "private synthetic quote"}]})
            self.assertTrue(store.workflow_checkpoint(rid, "call", {"critic": "completed"}, report=report,
                revision=0, generation=state["memory"]["generation"]))
            public = str(store.get("operator-alpha"))
            self.assertNotIn("qualityReports", public); self.assertNotIn("impersonation", public)
            private = store.inspect_quality("operator-alpha", rid)
            self.assertNotIn("private synthetic quote", str(private))
            with self.assertRaises(DemoError): store.inspect_quality("other-operator", rid)
            await store.transact(rid, revoke)
            self.assertFalse(store.workflow_checkpoint(rid, "call", {"critic": "completed"}, report=report,
                revision=0, generation=state["memory"]["generation"]))

class TestConfiguration(unittest.TestCase):
    def test_cloud_modes_fail_closed_without_touching_google(self):
        base = dict(_env_file=None, LOCAL_DEMO_ENABLED=True, FIRESTORE_ENABLED=True,
            HUGBACK_DEMO_STORE="firestore", HUGBACK_DEMO_PROJECT="synthetic-project",
            HUGBACK_AUTH_MODE="firebase", FIREBASE_PROJECT_ID="synthetic-project",
            HUGBACK_CLOUD_TEST_ENABLED=True, HUGBACK_TEST_OWNER_UIDS="allowed-operator")
        with patch.dict(os.environ, {"FIRESTORE_EMULATOR_HOST": ""}):
            Settings(**base).validate_test_mode()
            for changes in ({"HUGBACK_CLOUD_TEST_ENABLED": False}, {"HUGBACK_AUTH_MODE": "development"},
                            {"HUGBACK_TEST_OWNER_UIDS": ""}, {"HUGBACK_DEMO_DATABASE": "(default)"},
                            {"MEMORY_ENABLED": True}, {"FOLLOWUPS_ENABLED": True}, {"PORTAL_SHARING_ENABLED": True}):
                with self.subTest(changes=changes), self.assertRaises(ValueError): Settings(**(base|changes)).validate_test_mode()
            with patch.multiple(settings, **{k:v for k,v in base.items() if k != "_env_file"}):
                self.assertEqual(require_demo_identity(UserIdentity("allowed-operator", "firebase")), "firebase:allowed-operator")
                self.assertEqual(voice_owner(UserIdentity("allowed-operator", "firebase")), "firebase:allowed-operator")
                with self.assertRaises(DemoError): require_demo_identity(UserIdentity("stranger", "firebase"))
        with patch.dict(os.environ, {"FIRESTORE_EMULATOR_HOST": "127.0.0.1:8080"}):
            Settings(**(base|{"HUGBACK_DEMO_PROJECT": "demo-hugback", "HUGBACK_AUTH_MODE": "development"})).validate_test_mode()
            with self.assertRaises(ValueError): Settings(**base).validate_test_mode()

    def test_legacy_names_do_not_silently_change_model_or_auth(self):
        s = Settings(_env_file=None, ELARA_MODEL="synthetic-live", ELARA_AUTH_MODE="firebase", ELARA_VOICE_NAME="synthetic")
        self.assertEqual(s.HUGBACK_MODEL, "synthetic-live")
        self.assertEqual(s.HUGBACK_AUTH_MODE, "firebase")
        self.assertEqual(s.HUGBACK_VOICE_NAME, "synthetic")
        self.assertEqual(Settings(_env_file=None, ELARA_MODEL="old", HUGBACK_MODEL="new").HUGBACK_MODEL, "new")

if __name__ == "__main__": unittest.main()
