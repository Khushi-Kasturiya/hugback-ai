"""Firestore selection must fail closed; no ADC, network or SQLite I/O."""
import os
import unittest
from unittest.mock import Mock, patch

from app.config import Settings
from app.demo.service import get_demo_store


class FirestoreSelectionTests(unittest.TestCase):
    def setUp(self):
        self.config = Settings(
            _env_file=None,
            LOCAL_DEMO_ENABLED=True,
            HUGBACK_DEMO_STORE="firestore",
            FIRESTORE_ENABLED=True,
            HUGBACK_DEMO_PROJECT="synthetic-project",
            HUGBACK_DEMO_DATABASE="hugback-synthetic",
            FIREBASE_PROJECT_ID="synthetic-project",
            HUGBACK_AUTH_MODE="firebase",
            HUGBACK_CLOUD_TEST_ENABLED=True,
            HUGBACK_TEST_OWNER_UIDS="synthetic-operator",
            FIRESTORE_EMULATOR_HOST=None,
            MEMORY_ENABLED=False,
            FOLLOWUPS_ENABLED=False,
            CLOUD_INTAKE_ENABLED=False,
            PORTAL_SHARING_ENABLED=False,
            HUGBACK_WORKFLOW_ENABLED=False,
            HUGBACK_ALERT_EMAIL_ENABLED=False,
        )
        settings_patch = patch("app.demo.service.settings", self.config)
        settings_patch.start()
        self.addCleanup(settings_patch.stop)
        env_patch = patch.dict(os.environ, {"FIRESTORE_EMULATOR_HOST": ""})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        sqlite_patch = patch("app.demo.repository.SQLiteFamilyRepository")
        self.sqlite = sqlite_patch.start()
        self.addCleanup(sqlite_patch.stop)

    def tearDown(self):
        self.sqlite.assert_not_called()

    def test_named_firestore_repository_is_selected_without_local_path(self):
        repository = Mock()
        with patch("app.demo.service._firestore_repository", return_value=repository) as factory:
            store = get_demo_store()
        factory.assert_called_once_with("synthetic-project", "hugback-synthetic", "")
        self.assertIs(store.repository, repository)
        self.assertIsNone(store.path)

    def test_missing_credentials_do_not_fall_back_to_sqlite(self):
        with patch("app.demo.service._firestore_repository", side_effect=RuntimeError("ADC missing")):
            with self.assertRaisesRegex(RuntimeError, "ADC missing"):
                get_demo_store()

    def test_read_failure_does_not_fall_back_to_sqlite(self):
        repository = Mock()
        repository.transact.side_effect = TimeoutError("synthetic read failed")
        with patch("app.demo.service._firestore_repository", return_value=repository):
            store = get_demo_store()
        with self.assertRaisesRegex(TimeoutError, "synthetic read failed"):
            store.get("firebase:synthetic-operator")

    def test_missing_cloud_opt_in_blocks_before_repository_access(self):
        self.config.HUGBACK_CLOUD_TEST_ENABLED = False
        with patch("app.demo.service._firestore_repository") as factory:
            with self.assertRaises(ValueError):
                get_demo_store()
        factory.assert_not_called()
