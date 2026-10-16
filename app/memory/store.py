"""Durable Firestore storage for sessions and memory-processing state."""

import logging
from datetime import datetime
from typing import Any, Protocol

from app.config import settings
from app.memory.models import TranscriptTurn

logger = logging.getLogger("hugback.session_store")


class SessionStore(Protocol):
    enabled: bool

    async def save_session(
        self,
        user_id: str,
        session_id: str,
        started_at: datetime,
        ended_at: datetime,
        turns: list[TranscriptTurn],
    ) -> None: ...
    async def get_session(self, user_id: str, session_id: str) -> dict[str, Any] | None: ...
    async def update_status(
        self, user_id: str, session_id: str, status: str, error: str | None = None
    ) -> None: ...
    async def delete_user_data(self, user_id: str) -> None: ...


class DisabledSessionStore:
    enabled = False

    def __init__(self, reason: str | None = None) -> None:
        self.reason = reason

    async def save_session(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def get_session(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        return None

    async def update_status(
        self, user_id: str, session_id: str, status: str, error: str | None = None
    ) -> None:
        return None

    async def delete_user_data(self, user_id: str) -> None:
        return None


class FirestoreSessionStore:
    enabled = True

    def __init__(self) -> None:
        try:
            from google.cloud import firestore
        except ImportError as exc:
            raise RuntimeError(
                "google-cloud-firestore is required when Firestore is enabled"
            ) from exc
        self._firestore = firestore
        self._client = firestore.AsyncClient(
            project=settings.GOOGLE_CLOUD_PROJECT,
            database=settings.FIRESTORE_DATABASE,
        )

    def _document(self, user_id: str, session_id: str):
        return (
            self._client.collection("users")
            .document(user_id)
            .collection("sessions")
            .document(session_id)
        )

    async def save_session(
        self,
        user_id: str,
        session_id: str,
        started_at: datetime,
        ended_at: datetime,
        turns: list[TranscriptTurn],
    ) -> None:
        user_turns = sum(1 for turn in turns if turn.role == "user")
        await self._document(user_id, session_id).set(
            {
                "session_id": session_id,
                "user_id": user_id,
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_seconds": max(0, int((ended_at - started_at).total_seconds())),
                "turn_count": len(turns),
                "user_turn_count": user_turns,
                "transcript": [turn.model_dump(mode="python") for turn in turns],
                "memory_status": "pending" if user_turns else "skipped",
                "created_at": self._firestore.SERVER_TIMESTAMP,
            }
        )
        await (
            self._client.collection("users")
            .document(user_id)
            .set(
                {
                    "last_seen": self._firestore.SERVER_TIMESTAMP,
                    "session_count": self._firestore.Increment(1),
                },
                merge=True,
            )
        )

    async def get_session(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        snapshot = await self._document(user_id, session_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    async def update_status(
        self, user_id: str, session_id: str, status: str, error: str | None = None
    ) -> None:
        update: dict[str, Any] = {
            "memory_status": status,
            "memory_updated_at": self._firestore.SERVER_TIMESTAMP,
        }
        if error:
            update["memory_error"] = error[:1000]
        else:
            update["memory_error"] = self._firestore.DELETE_FIELD
        await self._document(user_id, session_id).update(update)

    async def delete_user_data(self, user_id: str) -> None:
        user_ref = self._client.collection("users").document(user_id)
        async for snapshot in user_ref.collection("sessions").stream():
            await snapshot.reference.delete()
        await user_ref.delete()


_session_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    global _session_store
    if _session_store is None:
        if not settings.FIRESTORE_ENABLED:
            _session_store = DisabledSessionStore("Firestore is not configured")
        else:
            try:
                _session_store = FirestoreSessionStore()
            except Exception as exc:
                # Session persistence must not make the real-time voice path
                # unavailable when an optional cloud dependency is unhealthy.
                logger.error("Firestore session storage is unavailable: %s", exc)
                _session_store = DisabledSessionStore(str(exc))
    return _session_store


def reset_session_store() -> None:
    """Clear the cached store; primarily useful for tests and health probes."""
    global _session_store
    _session_store = None
