import unittest
from pathlib import Path

from app.config import Settings


class CloudRunProfileTests(unittest.TestCase):
    def test_hosted_demo_enables_every_compatible_capability(self) -> None:
        profile = Path(__file__).resolve().parents[1] / ".env.cloud-run.example"
        configured = Settings(_env_file=profile)

        configured.validate_test_mode()

        for flag in (
            "LOCAL_DEMO_ENABLED",
            "FIRESTORE_ENABLED",
            "HUGBACK_CLOUD_TEST_ENABLED",
            "HUGBACK_REMOTE_TEST_ENABLED",
            "HUGBACK_PUBLIC_DEMO_ENABLED",
            "HUGBACK_JUDGE_DEMO_ENABLED",
            "HUGBACK_WORKFLOW_ENABLED",
            "HUGBACK_CONTEXT_EXTRACTION_ENABLED",
            "HUGBACK_REPLICATED_TTS_ENABLED",
            "HUGBACK_FIRESTORE_VOICE_RULES_CONFIRMED",
            "HUGBACK_ALERT_EMAIL_ENABLED",
        ):
            self.assertTrue(getattr(configured, flag), flag)

        # These are separate real-family/legacy data paths. Enabling any one of
        # them in the isolated synthetic Firestore deployment fails startup.
        for flag in (
            "MEMORY_ENABLED",
            "FOLLOWUPS_ENABLED",
            "CLOUD_INTAKE_ENABLED",
            "PORTAL_SHARING_ENABLED",
        ):
            self.assertFalse(getattr(configured, flag), flag)

    def test_hackathon_local_source_build_embeds_private_env_without_tracking_it(self) -> None:
        root = Path(__file__).resolve().parents[1]
        dockerfile = (root / "Dockerfile").read_text()
        dockerignore = (root / ".dockerignore").read_text().splitlines()
        gcloudignore = (root / ".gcloudignore").read_text().splitlines()
        gitignore = (root / ".gitignore").read_text().splitlines()

        self.assertIn("COPY .env* ./", dockerfile)
        self.assertIn("RUN if [ ! -f .env ]; then cp .env.example .env; fi", dockerfile)
        self.assertIn(".env", gitignore)
        self.assertNotIn(".env", dockerignore)
        self.assertNotIn(".env", gcloudignore)
        self.assertIn("!.env.example", dockerignore)
        self.assertIn("!.env.example", gcloudignore)


if __name__ == "__main__":
    unittest.main()
