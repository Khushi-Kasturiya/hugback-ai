"""Configuration settings for Hugback AI backend."""

import os
from pathlib import Path
from typing import Literal
from pydantic import Field
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
    HUGBACK_MODEL: str = "gemini-3.8-live"
    HUGBACK_VOICE_NAME: str = "Aoede"
    # Replicated voices are synthesized through the supported TTS endpoint;
    # the Voices endpoint itself must choose its creation model automatically.
    HUGBACK_TTS_MODEL: str = "gemini-3.8-flash-lite-tts"
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
    HUGBACK_AUTH_MODE: str = "development"
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
