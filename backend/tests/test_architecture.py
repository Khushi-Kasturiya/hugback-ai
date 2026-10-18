"""Content-free architecture manifest regression tests."""

import unittest
from unittest.mock import patch

from app.architecture import architecture_manifest
from app.config import settings


class ArchitectureManifestTests(unittest.TestCase):
    def test_firestore_is_canonical_and_local_stores_have_narrow_roles(self):
        with patch.object(settings, "HUGBACK_DEMO_STORE", "sqlite"):
            manifest = architecture_manifest()
        self.assertEqual(manifest["canonicalDeployment"]["operationalState"], "Cloud Firestore")
        self.assertEqual(manifest["runtime"]["familyState"], "sqlite_test_adapter")
        self.assertEqual(manifest["runtime"]["browserDrafts"], "indexeddb_private_preconsent_staging")
        self.assertNotIn("project", str(manifest).lower())
        self.assertNotIn("token", str(manifest).lower())

    def test_firestore_runtime_is_reported_without_claiming_probe_success(self):
        with patch.object(settings, "HUGBACK_DEMO_STORE", "firestore"):
            manifest = architecture_manifest()
        self.assertEqual(manifest["runtime"]["familyState"], "firestore")
        self.assertEqual(manifest["runtime"]["voiceSecrets"], "firestore_backend_only")
        self.assertTrue(any("Configured means" in note for note in manifest["notes"]))


if __name__ == "__main__":
    unittest.main()
