"""Storage latency regressions using a transactional double; no cloud I/O."""
import unittest
from datetime import timedelta
from unittest.mock import patch

from app.demo.models import CreateFamily, CreateRecipient
from app.demo.store import DemoError, now
from app.timing import stage_timer
from test_workflow import BASE, FakeFirestore, cloud_store


class FirestoreLatencyTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeFirestore()
        self.store = cloud_store(self.db)
        self.family = self.store.create("synthetic-owner", CreateFamily(**BASE, label="Mother"))
        self.family = self.store.add_recipient("synthetic-owner", CreateRecipient(**BASE, label="Father"))

    def test_owner_reads_batch_recipients_and_restore_requested_order(self):
        self.db.batch_reads.clear()
        family = self.store.get("synthetic-owner")
        self.assertEqual([r["label"] for r in family["recipients"]], ["Mother", "Father"])
        self.assertEqual(len(self.db.batch_reads), 1)
        self.assertEqual(len(self.db.batch_reads[0]), 2)

    def test_batch_read_still_rejects_wrong_owner_and_non_synthetic_records(self):
        rid = self.family["recipients"][1]["recipientId"]
        path = self.store.repository.RECIPIENTS + "/" + rid
        for key, value in (("owner", "f" * 64), ("syntheticOnly", False)):
            with self.subTest(key=key), patch.dict(self.db.data[path], {key: value}):
                with self.assertRaises(DemoError):
                    self.store.get("synthetic-owner")

    def test_missing_batch_result_fails_closed_without_alternate_reads(self):
        with patch.object(self.db, "get_all", return_value=iter([])):
            with self.assertRaises(DemoError):
                self.store.get("synthetic-owner")

    def test_duplicate_or_unrequested_batch_results_fail_closed(self):
        get_all = self.db.get_all
        def duplicated(refs, *, transaction):
            snapshots = list(get_all(refs, transaction=transaction))
            return iter([snapshots[0], snapshots[0]])
        def unrequested(refs, *, transaction):
            extra = self.db.collection(self.store.repository.RECIPIENTS).document(
                "demo-parent-" + "0" * 32)
            return get_all([*refs, extra], transaction=transaction)
        for replacement in (duplicated, unrequested):
            with self.subTest(replacement=replacement.__name__):
                with patch.object(self.db, "get_all", side_effect=replacement):
                    with self.assertRaises(DemoError):
                        self.store.get("synthetic-owner")

    def test_planner_status_and_activation_obey_same_lease(self):
        rid = self.family["recipients"][0]["recipientId"]
        self.store.start_call("synthetic-owner", "call", rid, 0)
        self.assertFalse(self.store.call_status(rid, "wrong-call", "active", planner_status="ready"))
        call = self.store.get("synthetic-owner")["recipients"][0]["calls"][-1]
        self.assertNotIn("workflow", call)
        self.assertTrue(self.store.call_status(rid, "call", "active", planner_status="fallback"))
        call = self.store.get("synthetic-owner")["recipients"][0]["calls"][-1]
        self.assertEqual(call["status"], "active")
        self.assertEqual(call["workflow"]["planner"], "fallback")
        with self.assertRaises(DemoError):
            self.store.call_status(rid, "call", "completed", planner_status="ready")

    def test_expired_activation_cannot_commit_planner_status(self):
        rid = self.family["recipients"][0]["recipientId"]
        self.store.start_call("synthetic-owner", "call", rid, 0)
        with patch("app.demo.store.now", return_value=now() + timedelta(hours=1)):
            self.assertFalse(self.store.call_status(rid, "call", "active", planner_status="ready"))
        call = self.store.get("synthetic-owner")["recipients"][0]["calls"][-1]
        self.assertEqual(call["status"], "connecting")
        self.assertNotIn("workflow", call)

    def test_stage_timing_never_logs_exception_content(self):
        with self.assertLogs("hugback.timing", "INFO") as log:
            with self.assertRaises(RuntimeError), stage_timer("synthetic_stage"):
                raise RuntimeError("private content must stay out of logs")
        self.assertIn("elapsed_ms=", log.output[0])
        self.assertIn("succeeded=False", log.output[0])
        self.assertNotIn("private content", log.output[0])
