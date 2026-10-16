"""Explicit opt-in, real loopback emulator only. Never live credentials/data."""
import os
import unittest
import uuid

from app.config import settings


@unittest.skipUnless(os.environ.get("HUGBACK_RUN_EMULATOR_TESTS") == "1",
                     "Actual Firestore emulator not requested")
class FirestoreEmulatorTests(unittest.TestCase):
    def test_repository_roundtrip_and_restart(self):
        from google.auth.credentials import AnonymousCredentials
        from google.cloud import firestore
        from app.demo.repository import FirestoreFamilyRepository
        from app.demo.store import DemoStore, DemoError
        from app.demo.models import CreateFamily
        settings.validate_test_mode()
        self.assertEqual(settings.HUGBACK_DEMO_STORE, "firestore")
        self.assertTrue(os.environ.get("FIRESTORE_EMULATOR_HOST"))
        self.assertTrue(settings.HUGBACK_DEMO_PROJECT.startswith("demo-"))
        client = firestore.Client(project=settings.HUGBACK_DEMO_PROJECT,
                                  database=settings.HUGBACK_DEMO_DATABASE,
                                  credentials=AnonymousCredentials())
        repo = FirestoreFamilyRepository(settings.HUGBACK_DEMO_PROJECT,
                                         settings.HUGBACK_DEMO_DATABASE, client=client)
        owner = "synthetic-emulator-" + uuid.uuid4().hex
        store = DemoStore(repository=repo)
        recipient = None
        try:
            family = store.create(owner, CreateFamily(
                syntheticOnly=True, simulateChildConsent=True, simulateParentConsent=True,
                enableMemory=True, label="Synthetic recipient"))
            recipient = family["recipients"][0]["recipientId"]
            self.assertEqual(DemoStore(repository=repo).get(owner)["familyId"], family["familyId"])
            store.start_call(owner, "one", recipient, 0)
            with self.assertRaises(DemoError): store.start_call(owner, "two", recipient, 0)
            self.assertTrue(store.call_status(recipient, "one", "completed", release=True))
            store.start_call(owner, "two", recipient, 0)
        finally:
            # Delete only documents owned by this test invocation, never a collection flush.
            client.collection(repo.FAMILIES).document(store.owner(owner)).delete()
            if recipient:
                client.collection(repo.RECIPIENTS).document(recipient).delete()
            client.close()
