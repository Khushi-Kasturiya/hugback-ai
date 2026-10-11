"""Consented voice validation, optional TTS replication and Live selection gates."""

from __future__ import annotations

import base64
import binascii
import io
import re
import wave
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Mapping

from app.config import settings

MAX_WAV_BYTES = 2 * 1024 * 1024
MAX_BASE64_CHARS = 4 * ((MAX_WAV_BYTES + 2) // 3)
MAX_RECORDING_SECONDS = 30
_SENTENCE_BOUNDARY = re.compile(r'(?<=[.!?।])["\'’”)]*(?:\s+|$)')


class VoiceEnrollmentError(ValueError):
    """The supplied voice material is malformed or unsafe to process."""


class VoiceConsentError(RuntimeError):
    """The experimental Live setup did not acknowledge voice consent."""


def require_live_consent_acknowledgement(setup_complete: Any) -> None:
    """Require the SDK's consent acknowledgement, never a likeness verdict.

    A missing signature does not diagnose provider entitlement or fallback.
    Never log or persist the signature.
    """
    consent = getattr(setup_complete, "voice_consent_signature", None)
    signature = getattr(consent, "signature", None)
    if not isinstance(signature, str) or not signature.strip():
        raise VoiceConsentError(
            "Voice replication is NOT verified: the Live setup did not return "
            "a consent-verification signature. Stopped before requesting speech "
            "or saving an output. This does not establish the cause; check "
            "provider support rather than treating default audio as a clone."
        )


def validate_call_voice_selection(
    voice_sample_audio: bytes | None,
    consent_audio: bytes | None,
    voice_id: str | None = None,
) -> None:
    """Reject ambiguous/unproven selection; never silently choose another voice."""
    if voice_id is not None:
        raise VoiceEnrollmentError(
            "Managed/TTS voice IDs are not enabled for ordinary Live calls. "
            "Use the separate compatibility probe."
        )
    if settings.ELARA_LIVE_VOICE_MODE == "preset":
        if voice_sample_audio is not None or consent_audio is not None:
            raise VoiceEnrollmentError(
                "This server uses a fixed preset voice. Remove the saved voice "
                "recordings from the test client before calling; no recording was uploaded to Google."
            )
    elif not voice_sample_audio or not consent_audio:
        raise VoiceEnrollmentError(
            "Experimental inline voice requires both recordings on every call; "
            "preset fallback is disabled."
        )


def parse_call_voice(message: Mapping[str, Any]) -> "InlineVoice | None":
    """Apply the server's voice mode before decoding or forwarding recordings."""
    if not isinstance(message, Mapping):
        raise VoiceEnrollmentError("Voice input must be a JSON object")
    if settings.ELARA_LIVE_VOICE_MODE == "preset" and (
        "voiceSampleAudio" in message or "consentAudio" in message
    ):
        # Presence itself is an error, including null/empty/stale browser fields.
        raise VoiceEnrollmentError(
            "This server uses a fixed preset voice. Remove the saved voice "
            "recordings from the test client before calling; no recording was uploaded to Google."
        )
    voice = parse_inline_voice(message)
    validate_call_voice_selection(
        voice.sample if voice else None, voice.consent if voice else None
    )
    return voice


@dataclass(frozen=True)
class WavRecording:
    data: bytes = field(repr=False)
    duration_seconds: float


@dataclass(frozen=True)
class InlineVoice:
    sample: bytes = field(repr=False)
    consent: bytes = field(repr=False)


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
        store=False,
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
    try:
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
    finally:
        # Closing the iterator alone does not close the SDK's HTTP SSE response.
        close = getattr(stream, "aclose", None) or getattr(stream, "close", None)
        if close:
            await close()


def validate_wav(
    data: bytes, *, label: str, minimum_seconds: float
) -> WavRecording:
    """Validate bounded, complete mono 24 kHz PCM16 WAV input."""
    if not isinstance(data, bytes) or not data:
        raise VoiceEnrollmentError(f"{label} must contain PCM WAV audio")
    if len(data) > MAX_WAV_BYTES:
        raise VoiceEnrollmentError(f"{label} exceeds the recording size limit")

    try:
        with wave.open(io.BytesIO(data), "rb") as source:
            if source.getnchannels() != 1:
                raise VoiceEnrollmentError(f"{label} must be mono")
            if source.getsampwidth() != 2 or source.getcomptype() != "NONE":
                raise VoiceEnrollmentError(f"{label} must use 16-bit PCM samples")
            if source.getframerate() != 24_000:
                raise VoiceEnrollmentError(f"{label} must be 24 kHz")

            frames = source.getnframes()
            duration = frames / source.getframerate()
            if not minimum_seconds <= duration <= MAX_RECORDING_SECONDS:
                raise VoiceEnrollmentError(
                    f"{label} must be {minimum_seconds:g}–30 seconds long"
                )
            # A WAV header can claim more frames than the payload actually holds.
            if len(source.readframes(frames)) != frames * 2:
                raise VoiceEnrollmentError(f"{label} contains truncated WAV audio")
    except (wave.Error, EOFError) as exc:
        raise VoiceEnrollmentError(
            f"{label} must be a readable PCM WAV recording"
        ) from exc

    return WavRecording(data=data, duration_seconds=duration)


def _decode_recording(value: Any, *, label: str, minimum_seconds: float) -> bytes:
    if not isinstance(value, str) or not value:
        raise VoiceEnrollmentError(f"{label} must be non-empty base64 audio")
    # Check before decoding so a large envelope cannot allocate unbounded audio.
    if len(value) > MAX_BASE64_CHARS:
        raise VoiceEnrollmentError(f"{label} exceeds the recording size limit")
    try:
        data = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise VoiceEnrollmentError(f"{label} must be valid base64 audio") from exc
    return validate_wav(
        data, label=label, minimum_seconds=minimum_seconds
    ).data


def parse_inline_voice(message: Mapping[str, Any]) -> InlineVoice | None:
    """Parse both recordings, or retain the preset voice if neither is supplied."""
    if not isinstance(message, Mapping):
        raise VoiceEnrollmentError("Voice input must be a JSON object")
    has_sample = "voiceSampleAudio" in message
    has_consent = "consentAudio" in message
    if not has_sample and not has_consent:
        return None
    if not has_sample or not has_consent:
        raise VoiceEnrollmentError("Both voice sample and consent audio are required")

    return InlineVoice(
        sample=_decode_recording(
            message["voiceSampleAudio"], label="Voice sample", minimum_seconds=10
        ),
        consent=_decode_recording(
            message["consentAudio"], label="Consent audio", minimum_seconds=2
        ),
    )


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
