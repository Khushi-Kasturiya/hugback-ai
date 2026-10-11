"""Turn-aware assembly of streaming Gemini transcription chunks."""

import re
from datetime import datetime, timezone

from app.memory.models import TranscriptTurn

_SPACE = re.compile(r"\s+")


def _clean(text: str) -> str:
    return _SPACE.sub(" ", text).strip()


def _merge(existing: str, chunk: str) -> str:
    """Merge either delta-style or cumulative transcription chunks."""
    chunk = _clean(chunk)
    if not chunk:
        return existing
    if not existing:
        return chunk
    if chunk == existing or existing.endswith(chunk):
        return existing
    if chunk.startswith(existing):
        return chunk
    if existing.startswith(chunk):
        return existing
    separator = "" if existing.endswith((" ", "-", "'")) else " "
    return _clean(f"{existing}{separator}{chunk}")


def merge_transcription(existing: str, chunk: str) -> str:
    """Merge streaming delta or cumulative transcription text."""
    return _merge(existing, chunk)


class TranscriptCollector:
    def __init__(self) -> None:
        self._pending_user = ""
        self._pending_model = ""
        self._user_started_at = None
        self._model_started_at = None
        self._turns: list[TranscriptTurn] = []

    def add_user(self, text: str) -> None:
        if not self._pending_user and text.strip():
            self._user_started_at = datetime.now(timezone.utc)
        self._pending_user = _merge(self._pending_user, text)

    def add_model(self, text: str) -> None:
        if not self._pending_model and text.strip():
            self._model_started_at = datetime.now(timezone.utc)
        self._pending_model = _merge(self._pending_model, text)

    def complete_turn(self) -> None:
        self._flush("user", self._pending_user, self._user_started_at)
        self._pending_user = ""
        self._user_started_at = None
        self._flush("model", self._pending_model, self._model_started_at)
        self._pending_model = ""
        self._model_started_at = None

    def latest_user_text(self) -> str:
        if self._pending_user:
            return self._pending_user
        return next((turn.text for turn in reversed(self._turns) if turn.role == "user"), "")

    def finalize(self) -> list[TranscriptTurn]:
        self.complete_turn()
        return list(self._turns)

    def _flush(self, role: str, text: str, timestamp=None) -> None:
        text = _clean(text)
        if not text:
            return
        self._turns.append(
            TranscriptTurn(
                role=role,
                text=text,
                timestamp=timestamp or datetime.now(timezone.utc),
                turn_index=len(self._turns),
            )
        )
