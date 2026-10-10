"""Validation for ephemeral, consented Gemini Live voice replication.

Voice recordings remain in the user's browser and are supplied only while a
Live session is being established. Elara does not persist the biometric audio.
"""

from __future__ import annotations

import base64
import binascii
import io
import wave
from dataclasses import dataclass
from typing import Any

MAX_RECORDING_BYTES = 5 * 1024 * 1024
MAX_BASE64_BYTES = ((MAX_RECORDING_BYTES + 2) // 3) * 4


class VoiceEnrollmentError(ValueError):
    """The supplied voice material is malformed or unsafe to process."""


@dataclass(frozen=True)
class ValidatedRecording:
    data: bytes
    duration_seconds: float


@dataclass(frozen=True)
class InlineVoice:
    sample: bytes
    consent: bytes


def validate_wav(
    data: bytes,
    *,
    label: str,
    minimum_seconds: float,
    maximum_seconds: float = 30.0,
) -> ValidatedRecording:
    """Validate Gemini's required mono, 24 kHz, PCM16 WAV format."""
    if not data:
        raise VoiceEnrollmentError(f"{label} recording is empty")
    if len(data) > MAX_RECORDING_BYTES:
        raise VoiceEnrollmentError(f"{label} recording exceeds the 5 MB limit")
    try:
        with wave.open(io.BytesIO(data), "rb") as source:
            channels = source.getnchannels()
            sample_width = source.getsampwidth()
            frame_rate = source.getframerate()
            frame_count = source.getnframes()
            compression = source.getcomptype()
    except (wave.Error, EOFError) as exc:
        raise VoiceEnrollmentError(f"{label} must be a readable PCM WAV file") from exc

    if compression != "NONE" or sample_width != 2:
        raise VoiceEnrollmentError(f"{label} must use uncompressed 16-bit PCM audio")
    if channels != 1:
        raise VoiceEnrollmentError(f"{label} must be mono")
    if frame_rate != 24_000:
        raise VoiceEnrollmentError(f"{label} must use a 24 kHz sample rate")

    duration = frame_count / frame_rate
    if not minimum_seconds <= duration <= maximum_seconds:
        raise VoiceEnrollmentError(
            f"{label} must be {minimum_seconds:g}–{maximum_seconds:g} seconds long"
        )
    return ValidatedRecording(data=data, duration_seconds=duration)


def _decode_recording(value: Any, label: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise VoiceEnrollmentError(f"{label} recording is missing")
    if len(value) > MAX_BASE64_BYTES:
        raise VoiceEnrollmentError(f"{label} recording exceeds the 5 MB limit")
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise VoiceEnrollmentError(f"{label} recording is not valid base64") from exc


from pathlib import Path

CONVERTED_VOICE_DIR = Path(__file__).resolve().parents[2] / "Voice" / "converted"
print("dir", CONVERTED_VOICE_DIR)


def get_local_fallback_voice() -> InlineVoice | None:
    """Load local pre-converted voice sample and consent audio from Voice/converted/ if present."""
    sample_path = CONVERTED_VOICE_DIR / "reference-24khz-mono.wav"
    consent_path = CONVERTED_VOICE_DIR / "consent-24khz-mono.wav"
    if sample_path.is_file() and consent_path.is_file():
        try:
            sample = validate_wav(sample_path.read_bytes(), label="Voice sample", minimum_seconds=10)
            consent = validate_wav(consent_path.read_bytes(), label="Consent", minimum_seconds=2)
            print(f"\n📁 [VOICE SERVICE] Loaded local converted voice files from disk: {sample_path.name} & {consent_path.name}", flush=True)
            return InlineVoice(sample=sample.data, consent=consent.data)
        except Exception as exc:
            print(f"⚠️ [VOICE SERVICE] Failed to load local converted voice files: {exc}", flush=True)
            return None
    return None


def parse_inline_voice(message: dict[str, Any]) -> InlineVoice | None:
    """Decode and validate the optional voice material in an auth envelope, falling back to disk files."""
    sample_value = message.get("voiceSampleAudio")
    consent_value = message.get("consentAudio")
    if sample_value is None and consent_value is None:
        return get_local_fallback_voice()
    if sample_value is None or consent_value is None:
        raise VoiceEnrollmentError("Both voice sample and consent recordings are required")
    print(f"\n🌐 [VOICE SERVICE] Received inline voice sample from WebSocket client", flush=True)
    sample = validate_wav(
        _decode_recording(sample_value, "Voice sample"),
        label="Voice sample",
        minimum_seconds=10,
    )
    consent = validate_wav(
        _decode_recording(consent_value, "Consent"),
        label="Consent",
        minimum_seconds=2,
    )
    return InlineVoice(sample=sample.data, consent=consent.data)


