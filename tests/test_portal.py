"""Synthetic, offline portal isolation tests. No provider calls or family data."""
import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.main import app
from app.config import settings
from app.portal.service import owner_key, read_shared_summaries, visible_summary


class SummaryVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.relationship = {
            "child_uid": "child-a", "parent_id": "parent-a", "status": "verified",
            "generation": 2, "verified_at": self.now - timedelta(days=1),
            "expires_at": self.now + timedelta(days=1),
        }
        self.summary = {
            "child_uid": "child-a", "parent_id": "parent-a", "relationship_generation": 2,
            "status": "approved", "approval_source": "verified_parent",
            "approved_text": "Please call this evening.",
            "approved_text_sha256": hashlib.sha256(b"Please call this evening.").hexdigest(),
            "call_ended_at": self.now - timedelta(minutes=10),
            "approved_at": self.now - timedelta(minutes=5),
            "expires_at": self.now + timedelta(hours=12),
            "private_transcript": "This must never be returned.",
        }

    def visible(self, uid="child-a"):
        return visible_summary("update-1", self.summary, self.relationship, uid, self.now)

    def test_only_exact_approved_text_is_returned(self):
        self.assertEqual(self.visible()["text"], "Please call this evening.")
        self.assertNotIn("private_transcript", self.visible())

    def test_other_child_parent_or_generation_is_denied(self):
        self.assertIsNone(self.visible("child-b"))
        for key, value in (("parent_id", "parent-b"), ("relationship_generation", 1)):
            with self.subTest(key=key):
                original = self.summary[key]
                self.summary[key] = value
                self.assertIsNone(self.visible())
                self.summary[key] = original

    def test_modified_unapproved_or_expired_text_is_denied(self):
        for key, value in (
            ("approved_text", "Different content"), ("status", "draft"),
            ("approval_source", "child_checkbox"), ("expires_at", self.now),
            ("approved_at", self.now + timedelta(seconds=1)), ("approved_at", "not-a-date"),
        ):
            with self.subTest(key=key):
                original = self.summary[key]
                self.summary[key] = value
                self.assertIsNone(self.visible())
                self.summary[key] = original

    def test_revoked_or_expired_relationship_is_denied(self):
        self.relationship["status"] = "revoked"
        self.assertIsNone(self.visible())
        self.relationship["status"] = "verified"
        self.relationship["expires_at"] = self.now
        self.assertIsNone(self.visible())


class PortalRouteTests(unittest.IsolatedAsyncioTestCase):
    async def request(self, path, headers=None, host="127.0.0.1"):
        transport = httpx.ASGITransport(app=app, client=(host, 1234))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path, headers=headers or {})

    async def test_development_never_reads_firestore_even_when_enabled(self):
        with patch.object(settings, "HUGBACK_AUTH_MODE", "development"), \
             patch.object(settings, "PORTAL_SHARING_ENABLED", True), \
             patch.object(settings, "FIRESTORE_ENABLED", True), \
             patch("app.portal.routes.read_shared_summaries", new_callable=AsyncMock) as read:
            response = await self.request("/api/portal/summaries", {"X-Hugback-Development-User": "synthetic-123"})
            self.assertEqual(response.json(), {"status": "development_only", "summaries": []})
            self.assertEqual(response.headers["cache-control"], "no-store")
            read.assert_not_awaited()

    async def test_development_denies_remote_requests_and_spoofed_forwarded_header(self):
        with patch.object(settings, "HUGBACK_AUTH_MODE", "development"):
            response = await self.request("/api/portal/status", {
                "X-Hugback-Development-User": "synthetic-123", "X-Forwarded-For": "127.0.0.1",
            }, host="203.0.113.1")
            self.assertEqual(response.status_code, 403)

    async def test_identity_required(self):
        with patch.object(settings, "HUGBACK_AUTH_MODE", "development"):
            self.assertEqual((await self.request("/api/portal/status")).status_code, 401)

    async def test_firebase_recipient_comes_from_verified_token_not_query(self):
        with patch.object(settings, "HUGBACK_AUTH_MODE", "firebase"), \
             patch.object(settings, "PORTAL_SHARING_ENABLED", True), \
             patch.object(settings, "FIRESTORE_ENABLED", True), \
             patch("app.auth._verify_firebase_id_token", return_value={"sub": "child-a"}), \
             patch("app.portal.routes.read_shared_summaries", new_callable=AsyncMock, return_value={"status": "ready", "summaries": []}) as read:
            response = await self.request("/api/portal/summaries?userId=child-b&parentId=parent-b", {"Authorization": "Bearer synthetic"})
            self.assertEqual(response.status_code, 200)
            read.assert_awaited_once_with("child-a")

    async def test_backend_failure_is_not_misreported_as_no_summaries(self):
        with patch.object(settings, "HUGBACK_AUTH_MODE", "firebase"), \
             patch.object(settings, "PORTAL_SHARING_ENABLED", True), \
             patch.object(settings, "FIRESTORE_ENABLED", True), \
             patch("app.auth._verify_firebase_id_token", return_value={"sub": "child-a"}), \
             patch("app.portal.routes.read_shared_summaries", new_callable=AsyncMock, side_effect=RuntimeError):
            response = await self.request("/api/portal/summaries", {"Authorization": "Bearer synthetic"})
            self.assertEqual(response.status_code, 503)

    async def test_invalid_firebase_token_does_not_fall_back(self):
        with patch.object(settings, "HUGBACK_AUTH_MODE", "firebase"), \
             patch("app.auth._verify_firebase_id_token", side_effect=ValueError):
            response = await self.request("/api/portal/status", {"Authorization": "Bearer synthetic", "X-Hugback-Development-User": "synthetic-123"})
            self.assertEqual(response.status_code, 401)

    async def test_unknown_auth_mode_is_denied(self):
        with patch.object(settings, "HUGBACK_AUTH_MODE", "typo"):
            response = await self.request("/api/portal/status", {"X-Hugback-Development-User": "synthetic-123"})
            self.assertEqual(response.status_code, 401)

    async def test_actual_mailbox_adapter_scopes_read_and_closes_client(self):
        client = MagicMock()
        fixture = SummaryVisibilityTests()
        fixture.setUp()
        snapshot = MagicMock()
        snapshot.exists = True
        snapshot.to_dict.return_value = {
            "relationship": fixture.relationship,
            "updates": [dict(fixture.summary, id="update-1")],
        }
        client.collection.return_value.document.return_value.get = AsyncMock(return_value=snapshot)
        client.close = AsyncMock()
        with patch("app.portal.service._new_client", return_value=client):
            result = await read_shared_summaries("child-a")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(len(result["summaries"]), 1)
        client.collection.assert_called_once_with("child_portal_mailboxes")
        client.collection.return_value.document.assert_called_once_with(owner_key("child-a"))
        client.close.assert_awaited_once()

    async def test_disabled_production_sharing_does_not_read_cloud(self):
        with patch.object(settings, "HUGBACK_AUTH_MODE", "firebase"), \
             patch.object(settings, "PORTAL_SHARING_ENABLED", False), \
             patch("app.auth._verify_firebase_id_token", return_value={"sub": "child-a"}), \
             patch("app.portal.routes.read_shared_summaries", new_callable=AsyncMock) as read:
            response = await self.request("/api/portal/summaries", {"Authorization": "Bearer synthetic"})
            self.assertEqual(response.json(), {"status": "not_configured", "summaries": []})
            read.assert_not_awaited()
