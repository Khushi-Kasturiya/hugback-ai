"""Synthetic call notices: consent, deterministic matching, and mocked SMTP."""

import asyncio
import ssl
import tempfile
import time
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from google.genai import types
from pydantic import ValidationError

from app.alerts.email import configured, send_call_summary, send_test_notice, send_test_probe
from app.alerts.smoke_test import main as smoke_main
from app.alerts.policy import asks_not_to_alert, detect_topic
from app.config import settings
from app.demo.models import CreateFamily, CreateRecipient, SetAlertSharing, SetAlertDestination
from app.demo.store import DemoError, DemoStore
from app.main import app
from app.memory.models import TranscriptTurn

BASE = dict(syntheticOnly=True, simulateChildConsent=True, simulateParentConsent=True,
            enableMemory=False, enableTranscriptSharing=True, enableAlertSharing=True)


def parent_words(text):
    return [TranscriptTurn(role="user", turn_index=0, text=text)]


class AlertTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.store = DemoStore(Path(temp.name) / "demo.sqlite3")
        for key, value in {
            "LOCAL_DEMO_DB_PATH": self.store.path,
            "LOCAL_DEMO_ENABLED": True,
            "HUGBACK_AUTH_MODE": "development",
            "HUGBACK_LIVE_VOICE_MODE": "preset",
            "HUGBACK_WORKFLOW_ENABLED": False,
            "HUGBACK_DEMO_STORE": "sqlite",
            "HUGBACK_ALERT_EMAIL_ENABLED": True,
            "HUGBACK_ALERT_SMTP_USERNAME": "sender@gmail.com",
            "HUGBACK_ALERT_SMTP_APP_PASSWORD": "synthetic-password",
        }.items():
            p = patch.object(settings, key, value); p.start(); self.addCleanup(p.stop)
        family = self.store.create("child-alert", CreateFamily(**BASE, label="Mother", relationship="mother"))
        family = self.store.add_recipient("child-alert", CreateRecipient(
            syntheticOnly=True, simulateChildConsent=True, simulateParentConsent=True,
            enableMemory=False, label="Father", relationship="father"))
        self.mother, self.father = [r["recipientId"] for r in family["recipients"]]
        self.store.set_alert_destination("child-alert", SetAlertDestination(
            syntheticOnly=True, familyId=family["familyId"], email="child@example.com",
            confirmTestRecipient=True))

    def recipient(self, rid):
        return next(r for r in self.store.get("child-alert")["recipients"] if r["recipientId"] == rid)

    def test_topic_matches_parent_self_reports_without_quoted_or_negated_mentions(self):
        for phrase in ("I have a fever today", "I'm feeling feverish", "Mujhe bukhar hai", "मुझे बुखार है"):
            self.assertEqual(detect_topic(parent_words(phrase)), "fever")
        for phrase in ("I don't have fever", "No fever now", "My son had fever last year",
                       "Do you have fever?", "The AI said fever"):
            self.assertIsNone(detect_topic(parent_words(phrase)))
        self.assertIsNone(detect_topic([TranscriptTurn(role="model", turn_index=0, text="I have fever")]))
        self.assertEqual(detect_topic(parent_words("My sister passed away today.")), "bereavement")
        self.assertTrue(asks_not_to_alert(parent_words("Please don't email my child about this.")))

    def test_consent_scoping_deduplication_and_revocation(self):
        mother = self.recipient(self.mother)
        self.assertTrue(mother["alertSharingEnabled"])
        internal = self.store.start_call("child-alert", "session-one", self.mother, mother["revision"])
        self.assertFalse(self.store.reserve_alert(self.father, "session-one", 0, "fever", email_configured=True))
        self.assertFalse(self.store.reserve_alert(self.mother, "session-one", 1, "fever", email_configured=True))
        self.assertTrue(self.store.record_transcript(self.mother, "session-one", 1, parent_words("I have fever")))
        self.assertTrue(self.store.reserve_alert(self.mother, "session-one", internal["alertSharing"]["generation"],
                                                 "fever", email_configured=True))
        self.assertFalse(self.store.reserve_alert(self.mother, "session-one", 1, "fever", email_configured=True))
        self.store.call_status(self.mother, "session-one", "completed", release=True)
        self.assertEqual(self.store.claim_alert_send(self.mother, "session-one", 1)["label"], "Mother")
        self.assertTrue(self.store.finish_alert_send(self.mother, "session-one", 1, delivered=True))
        self.assertEqual(self.recipient(self.mother)["calls"][0]["alert"]["status"], "sent")
        self.store.start_call("child-alert", "session-two", self.mother, mother["revision"])
        self.assertTrue(self.store.record_transcript(self.mother, "session-two", 1, parent_words("I have fever again")))
        self.assertFalse(self.store.reserve_alert(self.mother, "session-two", 1, "fever", email_configured=True))
        self.store.call_status(self.mother, "session-two", "completed", release=True)
        self.assertEqual(self.recipient(self.mother)["calls"][1]["alert"]["status"], "suppressed")
        self.store.set_alert_sharing("child-alert", SetAlertSharing(
            syntheticOnly=True, recipientId=self.mother, revision=mother["revision"], enabled=False))
        self.assertFalse(self.recipient(self.mother)["alertSharingEnabled"])
        self.assertNotIn("alert", self.recipient(self.mother)["calls"][0])
        self.assertFalse(self.recipient(self.father)["alertSharingEnabled"])

    def test_enabling_alerts_requires_separate_standing_consent_and_history(self):
        with self.assertRaises(ValidationError):
            SetAlertSharing(syntheticOnly=True, recipientId=self.father, revision=0,
                            enabled=True, simulateChildConsent=True)
        with self.assertRaises(DemoError):
            self.store.set_alert_sharing("child-alert", SetAlertSharing(
                syntheticOnly=True, recipientId=self.father, revision=0, enabled=True,
                simulateChildConsent=True, simulateParentConsent=True))

    def test_ui_email_requires_confirmation_and_family_scope(self):
        family = self.store.get("child-alert")
        self.assertTrue(family["alertEmailSelected"])
        self.assertTrue(family["alertEmailConfigured"])
        with self.assertRaises(ValidationError):
            SetAlertDestination(syntheticOnly=True, familyId=family["familyId"],
                                email="child@example.com", confirmTestRecipient=False)
        with self.assertRaises(DemoError):
            self.store.set_alert_destination("other-owner", SetAlertDestination(
                syntheticOnly=True, familyId=family["familyId"], email="child@example.com",
                confirmTestRecipient=True))
        with self.assertRaises(DemoError):
            self.store.set_alert_destination("child-alert", SetAlertDestination(
                syntheticOnly=True, familyId="demo-family-" + "0" * 32,
                email="child@example.com", confirmTestRecipient=True))
        self.assertNotIn("child@example.com", str(family))
        self.assertIn("child@example.com", self.store.path.read_bytes().decode("latin1"))
        cleared = self.store.set_alert_destination("child-alert", SetAlertDestination(
            syntheticOnly=True, familyId=family["familyId"], email=None))
        self.assertFalse(cleared["alertEmailSelected"])
        self.assertFalse(cleared["alertEmailConfigured"])

    def test_firestore_accepts_owner_scoped_destination_and_never_returns_raw_email(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "firestore-contract.sqlite3"
        values = {
            "HUGBACK_DEMO_STORE": "firestore", "HUGBACK_CLOUD_TEST_ENABLED": True,
            "HUGBACK_AUTH_MODE": "firebase",
        }
        patches = [patch.object(settings, key, value) for key, value in values.items()]
        for item in patches: item.start(); self.addCleanup(item.stop)
        store = DemoStore(path)
        family = store.create("firebase-owner", CreateFamily(
            **BASE, childName="Asha", childGender="female", label="Mother", relationship="mother"))
        family = store.set_alert_destination("firebase-owner", SetAlertDestination(
            syntheticOnly=True, familyId=family["familyId"], email="child@example.com",
            confirmTestRecipient=True))
        recipient = family["recipients"][0]
        self.assertTrue(family["alertEmailSelected"])
        self.assertTrue(family["alertEmailConfigured"])
        self.assertEqual(family["alertEmailHint"], "c***@example.com")
        self.assertNotIn("child@example.com", str(family))
        self.assertNotIn("child@example.com", str(family))
        internal = store.start_call("firebase-owner", "firestore-alert", recipient["recipientId"], 0)
        generation = internal["alertSharing"]["generation"]
        self.assertTrue(store.record_transcript(recipient["recipientId"], "firestore-alert", 1,
                                                parent_words("I have a fever today")))
        self.assertTrue(store.reserve_alert(recipient["recipientId"], "firestore-alert", generation,
                                            "fever", email_configured=True))
        store.call_status(recipient["recipientId"], "firestore-alert", "completed", release=True)
        claim = store.claim_alert_send(recipient["recipientId"], "firestore-alert", generation)
        self.assertEqual(claim["email"], "child@example.com")
        self.assertEqual(claim["childName"], "Asha")

    def test_browser_destination_route_is_owner_scoped_and_returns_only_masked_address(self):
        family = self.store.get("child-alert")
        payload = {"syntheticOnly": True, "familyId": family["familyId"],
                   "email": "child@example.com", "confirmTestRecipient": True}
        with TestClient(app, client=("127.0.0.1", 1234)) as client:
            headers = {"Origin": "http://127.0.0.1:3000", "X-Hugback-Development-User": "child-alert"}
            response = client.put("/api/demo/alert-destination", headers=headers, json=payload)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(response.json()["alertEmailConfigured"])
            self.assertNotIn("child@example.com", response.text)
            wrong = client.put("/api/demo/alert-destination", headers={
                **headers, "X-Hugback-Development-User": "other-owner"}, json=payload)
            self.assertNotEqual(wrong.status_code, 200)
            changed = client.put("/api/demo/alert-destination", headers=headers,
                                 json={**payload, "email": "another@example.com"})
            self.assertEqual(changed.status_code, 200)
            self.assertEqual(changed.json()["alertEmailHint"], "a***@example.com")
            self.assertNotIn("another@example.com", changed.text)
        with patch.object(settings, "HUGBACK_ALERT_EMAIL_ENABLED", False):
            self.assertFalse(self.store.get("child-alert")["alertEmailConfigured"])

    def test_unconfigured_and_failed_delivery_have_distinct_call_statuses(self):
        mother = self.recipient(self.mother)
        internal = self.store.start_call("child-alert", "without-smtp", self.mother, mother["revision"])
        generation = internal["alertSharing"]["generation"]
        self.assertTrue(self.store.record_transcript(self.mother, "without-smtp", 1,
                                                     parent_words("I have a fever today")))
        self.assertFalse(self.store.reserve_alert(self.mother, "without-smtp", generation,
                                                  "fever", email_configured=False))
        self.store.call_status(self.mother, "without-smtp", "completed", release=True)
        self.assertEqual(self.recipient(self.mother)["calls"][-1]["alert"]["status"], "not_configured")

        self.store.start_call("child-alert", "smtp-fails", self.mother, mother["revision"])
        self.assertTrue(self.store.record_transcript(self.mother, "smtp-fails", 1,
                                                     parent_words("I have a fever today")))
        self.assertTrue(self.store.reserve_alert(self.mother, "smtp-fails", generation,
                                                 "fever", email_configured=True))
        self.store.call_status(self.mother, "smtp-fails", "completed", release=True)
        self.assertIsNotNone(self.store.claim_alert_send(self.mother, "smtp-fails", generation))
        self.assertTrue(self.store.finish_alert_send(self.mother, "smtp-fails", generation,
                                                     delivered=False))
        self.assertEqual(self.recipient(self.mother)["calls"][-1]["alert"]["status"], "failed")

    def test_changing_family_email_cancels_pending_old_call_destination(self):
        family = self.store.get("child-alert")
        mother = self.recipient(self.mother)
        internal = self.store.start_call("child-alert", "before-address-change", self.mother,
                                         mother["revision"])
        generation = internal["alertSharing"]["generation"]
        self.assertTrue(self.store.record_transcript(self.mother, "before-address-change", 1,
                                                     parent_words("I have a fever today")))
        self.assertTrue(self.store.reserve_alert(self.mother, "before-address-change", generation,
                                                 "fever", email_configured=True))
        self.store.call_status(self.mother, "before-address-change", "completed", release=True)
        self.store.set_alert_destination("child-alert", SetAlertDestination(
            syntheticOnly=True, familyId=family["familyId"], email="new-child@example.com",
            confirmTestRecipient=True))
        self.assertIsNone(self.store.claim_alert_send(self.mother, "before-address-change", generation))
        self.assertEqual(self.recipient(self.mother)["calls"][-1]["alert"]["status"], "not_configured")

    def test_smtp_adapter_requires_operator_config_and_sends_only_brief_notice(self):
        values = {
            "HUGBACK_ALERT_EMAIL_ENABLED": True,
            "HUGBACK_ALERT_SMTP_USERNAME": "sender@gmail.com",
            "HUGBACK_ALERT_SMTP_APP_PASSWORD": "synthetic-password",
        }
        patches = [patch.object(settings, key, value) for key, value in values.items()]
        for item in patches: item.start(); self.addCleanup(item.stop)
        self.assertTrue(configured())
        with patch("app.alerts.email.smtplib.SMTP") as smtp:
            send_test_notice("Mother", "2026-10-13T10:00:00+00:00", "child@example.com", "Asha")
            client = smtp.return_value.__enter__.return_value
            client.starttls.assert_called_once()
            self.assertEqual(client.starttls.call_args.kwargs["context"].verify_mode, ssl.CERT_REQUIRED)
            client.login.assert_called_once_with("sender@gmail.com", "synthetic-password")
            message = client.send_message.call_args.args[0]
            self.assertEqual(message["To"], "child@example.com")
            self.assertIn("Hello Asha", message.get_content())
            self.assertIn("childportal", message.get_content())
            self.assertNotIn("fever", message.get_content().lower())
            self.assertNotIn("transcript", message.get_content().lower())
            send_test_probe("child@example.com")
            probe = client.send_message.call_args.args[0]
            self.assertEqual(probe["Subject"], "HugBack fictional email test")
            self.assertIn("not triggered by a call", probe.get_content())
            self.assertEqual(client.send_message.call_count, 2)

    def test_summary_email_contains_only_bounded_saved_summary(self):
        with patch("app.alerts.email.smtplib.SMTP") as smtp:
            summary = "Mother talked about gardening, and HugBack encouraged her to share more."
            send_call_summary("Mother", "2026-10-18T10:00:00+00:00",
                              "child@example.com", summary, "Asha")
            message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
            self.assertEqual(message["To"], "child@example.com")
            self.assertIn(summary, message.get_content())
            self.assertNotIn("transcript", message.get_content().lower())

    def test_summary_email_claim_is_once_only_and_invalidated_by_address_change(self):
        mother = self.recipient(self.mother)
        internal = self.store.start_call("child-alert", "summary-email", self.mother, mother["revision"])
        generation = internal["transcriptSharing"]["generation"]
        self.assertTrue(self.store.record_transcript(
            self.mother, "summary-email", generation, parent_words("I enjoyed the garden today.")))
        self.store.call_status(self.mother, "summary-email", "completed", release=True)
        self.assertTrue(self.store.record_call_summary(
            self.mother, "summary-email", generation,
            "Mother enjoyed the garden today and shared a calm conversation."))
        claim = self.store.claim_summary_email(self.mother, "summary-email", generation)
        self.assertEqual(claim["email"], "child@example.com")
        self.assertIsNone(self.store.claim_summary_email(self.mother, "summary-email", generation))
        self.assertTrue(self.store.finish_summary_email(
            self.mother, "summary-email", generation, delivered=True))
        call = self.recipient(self.mother)["calls"][-1]
        self.assertEqual(call["summaryEmailStatus"], "sent")

    def test_smoke_check_never_sends_without_explicit_flag(self):
        with (patch.object(settings, "HUGBACK_ALERT_EMAIL_ENABLED", False),
              patch("sys.argv", ["smoke_test"]),
              patch("app.alerts.smoke_test.send_test_probe") as sender,
              patch("builtins.print")):
            self.assertEqual(smoke_main(), 2)
            sender.assert_not_called()

        values = {
            "HUGBACK_ALERT_EMAIL_ENABLED": True,
            "HUGBACK_ALERT_SMTP_USERNAME": "sender@gmail.com",
            "HUGBACK_ALERT_SMTP_APP_PASSWORD": "synthetic-password",
        }
        patches = [patch.object(settings, key, value) for key, value in values.items()]
        for item in patches: item.start(); self.addCleanup(item.stop)
        with (patch("sys.argv", ["smoke_test"]),
              patch("app.alerts.smoke_test.send_test_probe") as sender,
              patch("builtins.print")):
            self.assertEqual(smoke_main(), 0)
            sender.assert_not_called()
        with (patch("sys.argv", ["smoke_test", "--send"]),
              patch("app.alerts.smoke_test.send_test_probe") as sender,
              patch("builtins.print")):
            self.assertEqual(smoke_main(), 2)
            sender.assert_not_called()
        with (patch("sys.argv", ["smoke_test", "--send", "--to", "child@example.com"]),
              patch("app.alerts.smoke_test.send_test_probe") as sender,
              patch("builtins.print")):
            self.assertEqual(smoke_main(), 0)
            sender.assert_called_once_with("child@example.com")

    def test_mock_call_saves_history_and_sends_one_notice_without_paid_io(self):
        class Live:
            def __init__(self): self.queue = asyncio.Queue()
            async def send_client_content(self, **kwargs):
                await self.queue.put(types.LiveServerMessage(server_content=types.LiveServerContent(
                    output_transcription=types.Transcription(text="I am HugBack, your AI companion."),
                    turn_complete=True)))
            async def receive(self): yield await self.queue.get()
        @asynccontextmanager
        async def connect(*, model, config): yield Live()
        provider = SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))
        envelope = {"type": "authenticate", "userId": "child-alert", "demoParent": True,
                    "demoRecipientId": self.mother, "demoRecipientRevision": 0}
        with (patch("app.main.create_genai_client", return_value=provider),
              patch("app.main.summarize_call", new=AsyncMock(return_value="Mother reported a fictional fever and HugBack responded.")),
              patch("app.main.alert_email_configured", return_value=True),
              patch("app.main.send_test_notice") as sender,
              patch("app.main.send_call_summary") as summary_sender,
              TestClient(app, client=("127.0.0.1", 1234)) as client):
            with client.websocket_connect("/ws", headers={"Origin": "http://127.0.0.1:3000"}) as ws:
                ws.send_json(envelope)
                self.assertEqual(ws.receive_json()["type"], "ready")
                ws.send_json({"type": "text", "text": "I have a fever today."})
                while not ws.receive_json().get("turnComplete"): pass
            deadline = time.monotonic() + 2
            call = self.recipient(self.mother)["calls"][-1]
            while call.get("alert", {}).get("status") != "sent" and time.monotonic() < deadline:
                time.sleep(0.01); call = self.recipient(self.mother)["calls"][-1]
            self.assertEqual(call["alert"]["status"], "sent")
            self.assertEqual(call["alert"]["category"], "fever")
            self.assertEqual(call["transcriptStatus"], "available")
            sender.assert_called_once()
            deadline = time.monotonic() + 2
            while call.get("summaryStatus") == "pending" and time.monotonic() < deadline:
                time.sleep(0.01); call = self.recipient(self.mother)["calls"][-1]
            self.assertEqual(call["summaryStatus"], "available")
            self.assertEqual(call["summaryEmailStatus"], "sent")
            summary_sender.assert_called_once()
            self.assertNotIn("turns", self.store.get_call_summary("child-alert", self.mother, call["sessionId"]))


if __name__ == "__main__": unittest.main()
