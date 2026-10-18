"""Cloud voice persistence/concurrency tests. No credentials, uploads or paid I/O."""
import asyncio
import contextlib
import json
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.voice.firestore_profiles import FirestoreVoiceProfileStore
from app.voice.profiles import get_voice_store, now
from app.voice.service import VoiceEnrollmentError
from test_remote_demo import CONFIG, ORIGIN
from test_voice_portal import enrollment
from test_workflow import FakeFirestore, cloud_store, BASE


def vault(db):
    store = FirestoreVoiceProfileStore(db)
    store.firestore = SimpleNamespace(transactional=db.transactional, SERVER_TIMESTAMP="server-timestamp")
    return store


class FirestoreVoiceTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeFirestore()
        self.store = vault(self.db)
        self.owner = "firebase:synthetic-owner"

    def save(self, key="voicekey_synthetic"):
        token = self.store.begin_enrollment(self.owner)
        return self.store.save(self.owner, key, enrollment_token=token)

    def test_restart_isolation_metadata_only_and_explicit_selection(self):
        profile = self.save()
        other_instance = vault(self.db)
        self.assertEqual(other_instance.get(self.owner), profile)
        self.assertFalse(profile["enabled"])
        self.assertNotIn("voicekey", json.dumps(profile))
        self.assertIsNone(other_instance.get("firebase:other-owner"))
        with self.assertRaises(VoiceEnrollmentError):
            other_instance.select("firebase:other-owner", profile["id"], True)
        with self.assertRaises(VoiceEnrollmentError):
            other_instance.resolve(self.owner, profile["id"])
        other_instance.select(self.owner, profile["id"], True)
        self.assertEqual(self.store.resolve(self.owner, profile["id"]), "voicekey_synthetic")
        self.assertNotIn(self.owner, json.dumps(self.db.data))

    def test_lease_blocks_other_instances_and_release_cannot_clear_new_lease(self):
        token = self.store.begin_enrollment(self.owner)
        other_instance = vault(self.db)
        self.assertTrue(other_instance.status(self.owner)["enrolling"])
        for op in (lambda: other_instance.begin_enrollment(self.owner),
                   lambda: other_instance.delete(self.owner),
                   lambda: other_instance.select(self.owner, "a" * 32, True)):
            with self.assertRaises(VoiceEnrollmentError):
                op()
        self.store.end_enrollment(self.owner, token)
        newer = other_instance.begin_enrollment(self.owner)
        self.store.end_enrollment(self.owner, token)
        self.assertTrue(self.store.status(self.owner)["enrolling"])
        with self.assertRaises(VoiceEnrollmentError):
            self.store.save(self.owner, "voicekey_stale", enrollment_token=token)
        other_instance.save(self.owner, "voicekey_new", enrollment_token=newer)

    def test_simultaneous_instances_only_one_acquires_lease(self):
        def acquire(_):
            try:
                return vault(self.db).begin_enrollment(self.owner)
            except VoiceEnrollmentError:
                return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            tokens = list(pool.map(acquire, range(8)))
        self.assertEqual(sum(token is not None for token in tokens), 1)

    def test_expired_lease_can_be_recovered_but_cannot_resurrect_deleted_key(self):
        token = self.store.begin_enrollment(self.owner)
        with patch("app.voice.firestore_profiles.now", return_value=now() + timedelta(minutes=3)):
            self.assertFalse(self.store.status(self.owner)["enrolling"])
            self.store.delete(self.owner)
            with self.assertRaises(VoiceEnrollmentError):
                self.store.save(self.owner, "voicekey_stale", enrollment_token=token)
            self.assertIsNone(self.store.get(self.owner))

    def test_replacement_delete_and_expiry_never_fall_back(self):
        first = self.save()
        self.store.select(self.owner, first["id"], True)
        second = self.save("voicekey_replacement")
        self.assertNotEqual(first["id"], second["id"])
        with self.assertRaises(VoiceEnrollmentError):
            self.store.resolve(self.owner, first["id"])
        self.store.select(self.owner, second["id"], True)
        with patch("app.voice.firestore_profiles.now", return_value=now() + timedelta(days=8)):
            expired = self.store.get(self.owner)
            self.assertTrue(expired["expired"])
            self.assertTrue(expired["enabled"])
            self.assertNotIn("voicekey_", json.dumps(self.db.data))
            with self.assertRaises(VoiceEnrollmentError):
                self.store.resolve(self.owner, second["id"])
        self.store.delete(self.owner)
        self.assertIsNone(self.store.get(self.owner))
        with self.assertRaises(VoiceEnrollmentError):
            self.store.resolve(self.owner, second["id"])

    def test_provider_expiry_validation_and_transaction_retries(self):
        token = self.store.begin_enrollment(self.owner)
        with self.assertRaises(VoiceEnrollmentError):
            self.store.save(self.owner, "voicekey_synthetic", now() - timedelta(seconds=1),
                            enrollment_token=token)
        self.db.abort_once = True
        profile = self.store.save(self.owner, "voicekey_synthetic", now() + timedelta(days=1),
                                  enrollment_token=token)
        self.assertEqual(profile["expirySource"], "provider")
        self.assertEqual(len(self.db.data), 1)
        self.assertFalse(self.store.status(self.owner)["enrolling"])

    def test_firestore_selection_fails_closed_never_opens_sqlite(self):
        with (
            patch.multiple(settings, **(CONFIG | {"HUGBACK_FIRESTORE_VOICE_RULES_CONFIRMED": True})),
            patch.dict(os.environ, {"FIRESTORE_EMULATOR_HOST": ""}),
            patch("app.voice.profiles.VoiceProfileStore") as sqlite,
            patch("app.demo.service._firestore_repository", side_effect=RuntimeError("offline")),
        ):
            with self.assertRaises(RuntimeError):
                get_voice_store()
            with patch.object(settings, "HUGBACK_FIRESTORE_VOICE_RULES_CONFIRMED", False):
                with self.assertRaises(VoiceEnrollmentError):
                    get_voice_store()
            sqlite.assert_not_called()


class FirestoreVoiceRouteTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.multiple(settings, **(CONFIG | {
            "HUGBACK_FIRESTORE_VOICE_RULES_CONFIRMED": True, "HUGBACK_REPLICATED_TTS_ENABLED": True,
            "GEMINI_API_KEY": "synthetic-offline",
        })))
        self.stack.enter_context(patch.dict(os.environ, {"FIRESTORE_EMULATOR_HOST": ""}))
        self.db = FakeFirestore()
        self.store = vault(self.db)
        self.family = cloud_store(self.db)
        for module in ("app.main", "app.voice.routes", "app.demo.routes", "app.portal.routes"):
            self.stack.enter_context(patch(f"{module}.get_voice_store", side_effect=lambda: vault(self.db)))
        for module in ("app.main", "app.demo.routes"):
            self.stack.enter_context(patch(f"{module}.get_demo_store", return_value=self.family))
        self.stack.enter_context(patch("app.auth._verify_firebase_id_token", side_effect=lambda t: {"sub": t}))
        self.provider = self.stack.enter_context(patch("app.voice.routes.provision_voice", new_callable=AsyncMock))
        self.provider.return_value = SimpleNamespace(key="voicekey_synthetic", expire_time=None)
        self.google = self.stack.enter_context(patch("app.main.create_genai_client"))
        self.sqlite = self.stack.enter_context(patch("app.voice.profiles.sqlite3.connect",
                                                   side_effect=AssertionError("No local vault")))
        self.client = self.stack.enter_context(TestClient(app, client=("192.0.2.9", 1234)))
        self.headers = {"Origin": ORIGIN, "Authorization": "Bearer visitor-a"}
        self.owner = "firebase:visitor-a"

    def create_profile(self):
        response = self.client.post("/api/voice/enroll", headers=self.headers, json=enrollment())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn("voicekey", response.text)
        return response.json()["profile"]

    def test_public_visitor_can_enroll_reload_select_and_delete_only_own_voice(self):
        profile = self.create_profile()
        status = self.client.get("/api/portal/status", headers=self.headers).json()
        self.assertEqual(status["voice"]["storage"], "firestore")
        self.assertEqual(status["voice"]["profile"], profile)
        self.assertNotIn("voicekey", json.dumps(status))
        other = self.headers | {"Authorization": "Bearer visitor-b"}
        self.assertIsNone(self.client.get("/api/voice/profile", headers=other).json()["profile"])
        body = {"profileId": profile["id"], "enabled": True}
        self.assertEqual(self.client.put("/api/voice/profile", headers=other, json=body).status_code, 409)
        self.assertEqual(self.client.put("/api/voice/profile", headers=self.headers, json=body).status_code, 200)
        with patch.object(settings, "HUGBACK_REPLICATED_TTS_ENABLED", False):
            self.assertEqual(self.client.delete("/api/voice/profile", headers=self.headers).status_code, 200)
        self.assertIsNone(self.store.get(self.owner))
        self.provider.assert_awaited_once()
        self.sqlite.assert_not_called()

    def test_remote_origin_identity_and_consent_checked_before_provider(self):
        for headers in ({}, {"Origin": ORIGIN},
                        self.headers | {"Origin": "https://evil.example"},
                        self.headers | {"Origin": ""}):
            self.assertIn(self.client.post("/api/voice/enroll", headers=headers,
                                           json=enrollment()).status_code, (401, 403))
        for field in ("adultOwnVoice", "consentToGoogleAndBilling"):
            self.assertEqual(self.client.post("/api/voice/enroll", headers=self.headers,
                             json=enrollment() | {field: False}).status_code, 422)
        self.provider.assert_not_called()
        self.assertEqual(self.db.data, {})

    def test_remote_lock_prevents_duplicate_upload_and_mutation_across_instances(self):
        self.store.begin_enrollment(self.owner)
        self.assertTrue(self.client.get("/api/voice/profile", headers=self.headers).json()["enrolling"])
        self.assertEqual(self.client.post("/api/voice/enroll", headers=self.headers,
                                          json=enrollment()).status_code, 409)
        self.assertEqual(self.client.delete("/api/voice/profile", headers=self.headers).status_code, 409)
        self.provider.assert_not_called()

    def test_provider_and_firestore_failures_are_redacted_and_never_retried(self):
        self.provider.side_effect = RuntimeError("voicekey_private audio-private")
        response = self.client.post("/api/voice/enroll", headers=self.headers, json=enrollment())
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private", response.text)
        self.provider.assert_awaited_once()
        self.assertFalse(self.store.status(self.owner)["enrolling"])
        self.provider.reset_mock()
        with patch("app.voice.routes.get_voice_store", side_effect=OSError("private-db-data")):
            response = self.client.post("/api/voice/enroll", headers=self.headers, json=enrollment())
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private", response.text)
        self.provider.assert_not_called()

    def test_cloud_save_failure_is_not_reported_as_provider_rejection_or_local_storage(self):
        with patch.object(FirestoreVoiceProfileStore, "save", side_effect=OSError("voicekey_private")):
            response = self.client.post("/api/voice/enroll", headers=self.headers, json=enrollment())
        self.assertEqual(response.status_code, 500)
        self.assertIn("Firestore voice setup", response.text)
        self.assertNotIn("voicekey_private", response.text)
        self.assertNotIn("local voice setup", response.text)
        self.provider.assert_awaited_once()
        self.assertFalse(self.store.status(self.owner)["enrolling"])
        self.assertIsNone(self.store.get(self.owner))

    def test_cleanup_failure_does_not_hide_successfully_saved_cloud_profile(self):
        with patch.object(FirestoreVoiceProfileStore, "end_enrollment", side_effect=OSError("private")):
            profile = self.create_profile()
        self.assertEqual(self.store.get(self.owner), profile)
        self.assertFalse(self.store.status(self.owner)["enrolling"])
        self.provider.assert_awaited_once()

    def test_local_firestore_configuration_also_uses_cloud_vault_not_sqlite(self):
        with (
            patch.multiple(settings, HUGBACK_REMOTE_TEST_ENABLED=False, HUGBACK_PUBLIC_DEMO_ENABLED=False,
                           HUGBACK_TEST_OWNER_UIDS="visitor-a", CORS_ORIGINS="http://127.0.0.1:3000"),
            TestClient(app, client=("127.0.0.1", 1234)) as local,
        ):
            response = local.post("/api/voice/enroll", json=enrollment(), headers={
                "Origin": "http://127.0.0.1:3000", "Authorization": "Bearer visitor-a",
            })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.store.get(self.owner), response.json()["profile"])
        self.assertIn(FirestoreVoiceProfileStore.COLLECTION, next(iter(self.db.data)))
        self.sqlite.assert_not_called()

    def test_child_voice_call_reaches_ready_from_cloud_profile_and_scoped_family(self):
        profile = self.create_profile()
        self.store.select(self.owner, profile["id"], True)
        response = self.client.post("/api/demo/family", headers=self.headers,
                                    json=BASE | {"enableMemory": False})
        recipient = response.json()["recipients"][0]
        response = self.client.put("/api/demo/recipient-voice", headers=self.headers, json={
            "syntheticOnly": True, "recipientId": recipient["recipientId"],
            "revision": recipient["revision"], "mode": "child", "profileId": profile["id"],
        })
        self.assertEqual(response.status_code, 200, response.text)
        recipient = response.json()["recipients"][0]

        class Live:
            async def receive(self):
                await asyncio.Event().wait()
                yield

        @contextlib.asynccontextmanager
        async def connect(**kwargs):
            yield Live()
        self.google.return_value = SimpleNamespace(
            aio=SimpleNamespace(live=SimpleNamespace(connect=connect), aclose=AsyncMock()), close=lambda: None,
        )
        auth = {"type": "authenticate", "idToken": "visitor-a", "demoParent": True,
                "demoRecipientId": recipient["recipientId"], "demoRecipientRevision": recipient["revision"],
                "voiceProfileId": profile["id"]}
        with self.client.websocket_connect("/ws", headers={"Origin": ORIGIN}) as ws:
            ws.send_json(auth)
            ready = ws.receive_json()
            self.assertEqual(ready["type"], "ready", ready)
            self.assertEqual(ready["voice"], "replicated")
            self.assertNotIn("voicekey", json.dumps(ready))
        self.google.assert_called_once()
        self.google.reset_mock()
        for changes in ({"idToken": "visitor-b"}, {"voiceProfileId": "a" * 32},
                        {"voiceKey": "voicekey_synthetic"}):
            with self.client.websocket_connect("/ws", headers={"Origin": ORIGIN}) as ws:
                ws.send_json(auth | changes)
                self.assertEqual(ws.receive_json()["type"], "error")
        self.google.assert_not_called()
        self.sqlite.assert_not_called()
