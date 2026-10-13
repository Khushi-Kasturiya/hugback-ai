"""Configuration settings for Hugback AI backend."""

import os
import re
from pathlib import Path
from typing import Literal
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Authentication: Supports both Gemini API Key (AI Studio) and Vertex AI ADC
    GEMINI_API_KEY: str | None = None
    GOOGLE_GENAI_USE_VERTEXAI: bool = False
    GOOGLE_CLOUD_PROJECT: str = "project-84a7c715-3d60-4253-acb"
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    GOOGLE_APPLICATION_CREDENTIALS: str | None = None

    # Target Live Model & Voice
    # Live API models (support bidiGenerateContent):
    #   gemini-3.8-live, gemini-2.5-flash-native-audio-preview-12-2025
    # Non-live models like gemini-2.0-flash-exp do NOT support bidiGenerateContent
    HUGBACK_MODEL: str = Field(default="gemini-3.8-live", validation_alias=AliasChoices("HUGBACK_MODEL", "ELARA_MODEL"))
    HUGBACK_VOICE_NAME: str = Field(default="Aoede", validation_alias=AliasChoices("HUGBACK_VOICE_NAME", "ELARA_VOICE_NAME"))
    # Replicated voices are synthesized through the supported TTS endpoint;
    # the Voices endpoint itself must choose its creation model automatically.
    HUGBACK_TTS_MODEL: str = "gemini-3.8-flash-lite-tts"
    # Small first phrase, then normal sentence batching. 0 lookahead restores
    # serial synthesis; 1 overlaps one already-generated phrase, not new content.
    HUGBACK_TTS_FIRST_PHRASE_CHARS: int = Field(default=96, ge=48, le=280)
    HUGBACK_TTS_LOOKAHEAD: int = Field(default=1, ge=0, le=1)
    # Give a caller's natural mid-sentence pause room before Live closes a turn.
    HUGBACK_END_OF_SPEECH_SILENCE_MS: int = Field(default=1000, ge=700, le=1600)
    # Explicit portal TTS capability; never inferred from old browser recordings
    # or enabled solely by the local call simulator.
    HUGBACK_REPLICATED_TTS_ENABLED: bool = False
    # Private single-machine vault; no raw recordings and no cloud fallback.
    HUGBACK_VOICE_DB_PATH: Path = Path(__file__).resolve().parent.parent / ".local-voice" / "voices.sqlite3"
    # Never infer the call's voice mode from browser storage. Experimental mode
    # requires both recordings on every call and must never fall back to a preset.
    HUGBACK_LIVE_VOICE_MODE: Literal["preset", "experimental-inline"] = "preset"

    # Optional inputs for the isolated voice test script, NOT a global caller
    # voice. Merely configuring these paths must never upload any recordings.
    HUGBACK_VOICE_REFERENCE_PATH: Path | None = None
    HUGBACK_VOICE_CONSENT_PATH: Path | None = None
    HUGBACK_VOICE_TEST_OUTPUT_PATH: Path | None = None

    # Identity. Use "firebase" in deployed environments. Development mode
    # accepts only a constrained, browser-generated ID and must never be used
    # as an authorization boundary in production.
    HUGBACK_AUTH_MODE: Literal["development", "firebase"] = Field(
        default="development", validation_alias=AliasChoices("HUGBACK_AUTH_MODE", "ELARA_AUTH_MODE"))
    FIREBASE_PROJECT_ID: str | None = None

    # Long-term memory and durable session storage.
    MEMORY_ENABLED: bool = False
    MEMORY_BANK_NAME: str | None = None
    MEMORY_INITIAL_LIMIT: int = 5
    MEMORY_SEARCH_LIMIT: int = 3
    MEMORY_CONTEXT_MAX_CHARS: int = 4000
    FIRESTORE_ENABLED: bool = False
    FIRESTORE_DATABASE: str = "(default)"

    # Read-only recipient mailbox. Requires Firebase auth, Firestore, trusted
    # parent/child enrollment and exact-content parent approval; never a UUID.
    PORTAL_SHARING_ENABLED: bool = False

    # Synthetic, loopback-only hackathon simulator. Never a production store.
    LOCAL_DEMO_ENABLED: bool = False
    LOCAL_DEMO_DB_PATH: Path = Path(__file__).resolve().parent.parent / ".local-demo" / "hugback.sqlite3"
    # Explicit synthetic test storage; never redirects production collections.
    HUGBACK_DEMO_STORE: Literal["sqlite", "firestore"] = "sqlite"
    FIRESTORE_EMULATOR_HOST: str | None = None
    HUGBACK_DEMO_PROJECT: str = ""
    HUGBACK_DEMO_DATABASE: str = "hugback-synthetic"
    HUGBACK_CLOUD_TEST_ENABLED: bool = False
    HUGBACK_TEST_OWNER_UIDS: str = ""
    # Planner + Critic only for acknowledged synthetic calls, not real-family analysis.
    HUGBACK_WORKFLOW_ENABLED: bool = False

    # Optional Gmail SMTP notices for local fictional calls. Family setup may
    # select a test address in local SQLite; it is not verified child identity.
    HUGBACK_ALERT_EMAIL_ENABLED: bool = False
    HUGBACK_ALERT_SMTP_USERNAME: str = ""
    HUGBACK_ALERT_SMTP_APP_PASSWORD: str = ""

    # Internal Forms/Drive intake storage only; no browser route or consent grant.
    # Requires pre-existing resources. Enabling Firestore alone does not upload.
    CLOUD_INTAKE_ENABLED: bool = False
    # Existing bucket name only, no gs:// prefix, object path, URL or credentials.
    CLOUD_IMPORT_BUCKET: str = ""

    # Canonical wellbeing follow-up pilot; off until provider/enrollment gates
    # are validated. Per-owner, versioned consent is ALSO required in Firestore.
    FOLLOWUPS_ENABLED: bool = False
    FOLLOWUP_EXTRACTION_MODEL: str = "gemini-3.8-flash"
    FOLLOWUP_COOLDOWN_HOURS: int = Field(default=24, ge=1, le=168)
    FOLLOWUP_RETENTION_HOURS: int = Field(default=72, ge=1, le=168)

    # Post-call processing. "inline" is convenient locally; "cloud_tasks"
    # is durable on Cloud Run and is the required production setting.
    MEMORY_PROCESSING_MODE: str = "inline"
    CLOUD_TASKS_LOCATION: str = "us-central1"
    CLOUD_TASKS_QUEUE: str = "hugback-memory"
    MEMORY_PROCESSOR_URL: str | None = None
    CLOUD_TASKS_SERVICE_ACCOUNT: str | None = None
    MEMORY_TASK_SECRET: str | None = None

    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    LOG_LEVEL: str = "INFO"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def firebase_project(self) -> str:
        return self.FIREBASE_PROJECT_ID or self.GOOGLE_CLOUD_PROJECT

    def validate_test_mode(self) -> None:
        """No I/O. Run on startup and at every synthetic test entry point."""
        if self.HUGBACK_ALERT_EMAIL_ENABLED and not self.LOCAL_DEMO_ENABLED:
            raise ValueError("SMTP topic notices are limited to the synthetic simulator")
        if self.HUGBACK_WORKFLOW_ENABLED and not self.LOCAL_DEMO_ENABLED:
            raise ValueError("The four-role workflow currently requires the synthetic simulator")
        from urllib.parse import urlparse
        emulator = self.FIRESTORE_EMULATOR_HOST or os.environ.get("FIRESTORE_EMULATOR_HOST", "")
        if emulator:
            parsed = urlparse("//" + emulator)
            if (parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or not parsed.port
                    or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
                raise ValueError("The Firestore emulator must be a loopback host:port, without a URL path")
            if self.HUGBACK_DEMO_STORE != "firestore":
                raise ValueError("Unset FIRESTORE_EMULATOR_HOST outside explicit Firestore test mode")
        if self.HUGBACK_DEMO_STORE != "firestore":
            return
        if not self.LOCAL_DEMO_ENABLED or not self.FIRESTORE_ENABLED:
            raise ValueError("Firestore test storage requires LOCAL_DEMO_ENABLED and FIRESTORE_ENABLED")
        if (not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", self.HUGBACK_DEMO_PROJECT)
                or not re.fullmatch(r"[a-z][a-z0-9-]{2,61}[a-z0-9]", self.HUGBACK_DEMO_DATABASE)):
            raise ValueError("Select an explicit test project and a dedicated named test database")
        if any((self.MEMORY_ENABLED, self.FOLLOWUPS_ENABLED, self.CLOUD_INTAKE_ENABLED, self.PORTAL_SHARING_ENABLED)):
            raise ValueError("Synthetic Firestore mode cannot enable production/legacy data paths")
        if emulator:
            if not self.HUGBACK_DEMO_PROJECT.startswith("demo-") or self.HUGBACK_AUTH_MODE != "development":
                raise ValueError("Emulator tests require a demo-* project and development auth")
        elif not (
            self.HUGBACK_CLOUD_TEST_ENABLED and self.HUGBACK_AUTH_MODE == "firebase"
            and self.FIREBASE_PROJECT_ID == self.HUGBACK_DEMO_PROJECT
            and self.HUGBACK_TEST_OWNER_UIDS.strip()
        ):
            raise ValueError("Live test storage requires explicit cloud opt-in, matching Firebase project and an owner allowlist")


settings = Settings()

# Populate Google environment variables
if settings.GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = settings.GEMINI_API_KEY
if settings.GOOGLE_GENAI_USE_VERTEXAI:
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
    os.environ["GOOGLE_CLOUD_PROJECT"] = settings.GOOGLE_CLOUD_PROJECT
    os.environ["GOOGLE_CLOUD_LOCATION"] = settings.GOOGLE_CLOUD_LOCATION
if settings.GOOGLE_APPLICATION_CREDENTIALS:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.GOOGLE_APPLICATION_CREDENTIALS

# Do not install an arbitrary endpoint from configuration. Validate test mode first.
if settings.FIRESTORE_EMULATOR_HOST:
    settings.validate_test_mode()
    os.environ["FIRESTORE_EMULATOR_HOST"] = settings.FIRESTORE_EMULATOR_HOST
