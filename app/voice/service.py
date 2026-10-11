"""Validation and provisioning helpers for consented voice replication."""

from __future__ import annotations

import base64
import binascii
import io
import re
import wave
from dataclasses import dataclass
from typing import Any, AsyncIterator

MAX_RECORDING_BYTES = 5 * 1024 * 1024
MAX_BASE64_BYTES = ((MAX_RECORDING_BYTES + 2) // 3) * 4
_SENTENCE_BOUNDARY = re.compile(r'(?<=[.!?])[\"\'’”)]*(?:\s+|$)')


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


@dataclass(frozen=True)
class SynthesizedAudio:
    pcm: bytes
    sample_rate: int


def split_ready_speech(
    text: str,
    *,
    final: bool = False,
    maximum_chars: int = 280,
) -> tuple[list[str], str]:
    """Take complete, reasonably sized phrases from streaming transcription.

    Waiting for sentence punctuation avoids a paid TTS request for every token,
    while the size cap prevents a punctuation-light response from blocking audio
    until the entire model turn has completed.
    """
    remaining = text.lstrip()
    ready: list[str] = []
    while remaining:
        boundary = _SENTENCE_BOUNDARY.search(remaining)
        if boundary and boundary.end() <= maximum_chars:
            cut = boundary.end()
        elif len(remaining) > maximum_chars:
            cut = remaining.rfind(" ", 0, maximum_chars + 1)
            if cut <= 0:
                cut = maximum_chars
        else:
            break
        segment = remaining[:cut].strip()
        remaining = remaining[cut:].lstrip()
        if segment:
            ready.append(segment)

    if final and remaining.strip():
        ready.append(remaining.strip())
        remaining = ""
    return ready, remaining


def create_replicated_voice_key(
    client: Any,
    recordings: InlineVoice,
) -> str:
    """Create a private seven-day Gemini voice key for the validated speaker.

    The Voices API selects its replication model server-side. Supplying a TTS
    synthesis model here currently causes INVALID_ARGUMENT, and the returned
    key remains usable with every supported synthesis model.
    """
    voice = client.voices.create(
        store=False,
        voice={
            "type": "replicated",
            "replicated": {
                "source_audio": {
                    "mime_type": "audio/wav",
                    "data": base64.b64encode(recordings.sample).decode("ascii"),
                },
                "consent_audio": {
                    "mime_type": "audio/wav",
                    "data": base64.b64encode(recordings.consent).decode("ascii"),
                },
            },
        },
    )
    if not voice.key:
        raise RuntimeError("Google did not return a replicated voice key")
    return voice.key


def _decode_synthesized_audio(value: Any) -> SynthesizedAudio:
    if isinstance(value, str):
        try:
            audio = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError("Google returned invalid synthesized audio") from exc
    elif isinstance(value, bytes):
        audio = value
    else:
        raise RuntimeError("Google returned no synthesized audio")

    if audio.startswith(b"RIFF"):
        try:
            with wave.open(io.BytesIO(audio), "rb") as source:
                if source.getnchannels() != 1 or source.getsampwidth() != 2:
                    raise RuntimeError("Google returned an unsupported audio format")
                return SynthesizedAudio(
                    pcm=source.readframes(source.getnframes()),
                    sample_rate=source.getframerate(),
                )
        except wave.Error as exc:
            raise RuntimeError("Google returned an invalid WAV response") from exc

    # Gemini TTS currently emits 24 kHz mono PCM when the response is not a
    # WAV container.
    return SynthesizedAudio(pcm=audio, sample_rate=24_000)


async def synthesize_replicated_speech(
    client: Any,
    *,
    voice_key: str,
    text: str,
    model: str,
) -> SynthesizedAudio:
    """Synthesize one completed agent turn using a replicated Gemini voice."""
    interaction = await client.aio.interactions.create(
        api_version="v1beta",
        model=model,
        input=[{
            "type": "user_input",
            "content": [{
                "type": "text",
                "text": text,
                "annotations": [{
                    "type": "speech_metadata",
                    "style": "warm, natural, caring, and conversational",
                }],
            }],
        }],
        response_format={"type": "audio"},
        generation_config={"speech_config": [{"voice": voice_key}]},
    )
    output_audio = getattr(interaction, "output_audio", None)
    return _decode_synthesized_audio(getattr(output_audio, "data", None))


async def stream_replicated_speech(
    client: Any,
    *,
    voice_key: str,
    text: str,
    model: str,
) -> AsyncIterator[SynthesizedAudio]:
    """Yield raw PCM chunks as Google synthesizes the replicated voice."""
    stream = await client.aio.interactions.create(
        api_version="v1beta",
        model=model,
        input=[{
            "type": "user_input",
            "content": [{
                "type": "text",
                "text": text,
                "annotations": [{
                    "type": "speech_metadata",
                    "style": "warm, natural, caring, and conversational",
                }],
            }],
        }],
        response_format={"type": "audio", "mime_type": "audio/l16"},
        generation_config={"speech_config": [{"voice": voice_key}]},
        store=False,
        stream=True,
    )
    async for event in stream:
        if getattr(event, "event_type", None) != "step.delta":
            continue
        delta = getattr(event, "delta", None)
        if getattr(delta, "type", None) != "audio":
            continue
        data = getattr(delta, "data", None)
        if not data:
            continue
        try:
            pcm = base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError("Google returned invalid streaming audio") from exc
        if pcm:
            yield SynthesizedAudio(
                pcm=pcm,
                sample_rate=getattr(delta, "sample_rate", None) or 24_000,
            )


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


def parse_inline_voice(message: dict[str, Any]) -> InlineVoice | None:
    """Decode and validate voice material submitted during enrollment."""
    sample_value = message.get("voiceSampleAudio")
    consent_value = message.get("consentAudio")
    if sample_value is None and consent_value is None:
        return None
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


def parse_voice_key(message: dict[str, Any]) -> str | None:
    """Accept only a Google-issued replicated voice ID or stateless key."""
    value = message.get("voiceKey")
    if value is None:
        return None
    if not isinstance(value, str) or not value.startswith(("voice_", "voicekey_")):
        raise VoiceEnrollmentError("The replicated voice key is invalid")
    if len(value) > 524_288 or not value.isascii():
        raise VoiceEnrollmentError("The replicated voice key is invalid")
    return value


