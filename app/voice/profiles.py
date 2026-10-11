"""Single-machine voice vault, separate from synthetic family/memory records."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sqlite3
import uuid
from urllib.parse import urlparse

from app.config import settings
from app.voice.service import VoiceEnrollmentError, parse_voice_key


def now():
    return datetime.now(timezone.utc)


def enrollment_available():
    return (
        settings.HUGBACK_REPLICATED_TTS_ENABLED
        and settings.HUGBACK_AUTH_MODE.lower() == "development"
        and settings.HUGBACK_LIVE_VOICE_MODE == "preset"
        and bool(settings.GEMINI_API_KEY)
    )


def require_local_voice(peer, origin, *, mutation=True):
    # Deletes/reads must remain possible after the enrollment feature is disabled.
    parsed = urlparse(origin or "")
    if settings.HUGBACK_AUTH_MODE.lower() != "development" or peer not in {"127.0.0.1", "::1"}:
        raise VoiceEnrollmentError("Voice setup is currently a localhost development feature.")
    if origin is not None or mutation:
        if (
            origin not in settings.cors_origins_list
            or parsed.scheme not in {"http", "https"}
            or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        ):
            raise VoiceEnrollmentError("Use the configured local frontend origin for voice setup.")


class VoiceProfileStore:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.fchmod(descriptor, 0o600)
        os.close(descriptor)
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA secure_delete=ON")
            conn.execute("""CREATE TABLE IF NOT EXISTS voices (
                owner TEXT PRIMARY KEY, profile_id TEXT NOT NULL,
                voice_key TEXT, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                enabled INTEGER NOT NULL, expiry_source TEXT NOT NULL
            )""")
            # Keep expired metadata/selection so expiry cannot silently select preset.
            conn.execute("UPDATE voices SET voice_key=NULL WHERE expires_at<=?", (now().isoformat(),))
            conn.commit()
            yield conn
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def public(row):
        if row is None:
            return None
        return {
            "id": row["profile_id"], "createdAt": row["created_at"],
            "expiresAt": row["expires_at"], "enabled": bool(row["enabled"]),
            "expired": not row["voice_key"], "expirySource": row["expiry_source"],
        }

    def get(self, owner):
        with self.connection() as conn:
            return self.public(conn.execute("SELECT * FROM voices WHERE owner=?", (owner,)).fetchone())

    def save(self, owner, key, provider_expiry=None):
        if not parse_voice_key({"voiceKey": key}) or not key.startswith("voicekey_"):
            raise VoiceEnrollmentError("Google did not return a client-managed voice key.")
        created = now()
        expires = created + timedelta(days=7)  # Local retention cap, not an entitlement promise.
        source = "local_limit"
        if provider_expiry is not None:
            if not isinstance(provider_expiry, datetime) or provider_expiry.tzinfo is None:
                raise VoiceEnrollmentError("Google returned an invalid voice expiry.")
            expires = min(expires, provider_expiry.astimezone(timezone.utc))
            source = "provider" if expires == provider_expiry else "local_limit"
        if expires <= created:
            raise VoiceEnrollmentError("Google returned an already expired voice.")
        with self.connection() as conn:
            conn.execute("INSERT OR REPLACE INTO voices VALUES (?, ?, ?, ?, ?, ?, ?)", (
                owner, uuid.uuid4().hex, key, created.isoformat(), expires.isoformat(), 0, source,
            ))
        return self.get(owner)

    def select(self, owner, profile_id, enabled):
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM voices WHERE owner=?", (owner,)).fetchone()
            if row is None or row["profile_id"] != profile_id:
                raise VoiceEnrollmentError("Voice setup changed. Refresh the portal.")
            if enabled and not row["voice_key"]:
                raise VoiceEnrollmentError("This voice expired. Upload fresh recordings first.")
            conn.execute("UPDATE voices SET enabled=? WHERE owner=?", (int(enabled), owner))
        return self.get(owner)

    def delete(self, owner):
        with self.connection() as conn:
            conn.execute("DELETE FROM voices WHERE owner=?", (owner,))

    def resolve(self, owner, profile_id):
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM voices WHERE owner=?", (owner,)).fetchone()
            if not row or row["profile_id"] != profile_id or not row["enabled"]:
                raise VoiceEnrollmentError("The selected voice is no longer active. Refresh Voice setup.")
            if not row["voice_key"]:
                raise VoiceEnrollmentError("The selected voice expired. Re-enroll or choose the standard voice.")
            return row["voice_key"]


def get_voice_store():
    return VoiceProfileStore(settings.HUGBACK_VOICE_DB_PATH)
