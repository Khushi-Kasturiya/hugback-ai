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


class TranscriptCollector:
    def __init__(self) -> None:
        self._pending_user = ""
        self._pending_model = ""
        self._turns: list[TranscriptTurn] = []

    def add_user(self, text: str) -> None:
        self._pending_user = _merge(self._pending_user, text)

    def add_model(self, text: str) -> None:
        self._pending_model = _merge(self._pending_model, text)

    def complete_turn(self) -> None:
        self._flush("user", self._pending_user)
        self._pending_user = ""
        self._flush("model", self._pending_model)
        self._pending_model = ""

    def finalize(self) -> list[TranscriptTurn]:
        self.complete_turn()
        return list(self._turns)

    def _flush(self, role: str, text: str) -> None:
        text = _clean(text)
        if not text:
            return
        self._turns.append(
            TranscriptTurn(
                role=role,
                text=text,
                timestamp=datetime.now(timezone.utc),
                turn_index=len(self._turns),
            )
        )
