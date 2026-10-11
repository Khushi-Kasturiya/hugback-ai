#!/usr/bin/env python3
"""Offline-first compatibility probe for Gemini Live voice replication.

No recordings leave the machine unless --run-live and --confirm-consent are both
supplied. The Cloud PCM documentation and the installed SDK's WAV schema differ;
choose a wire format explicitly for a real inline probe. Successful local
validation does not prove speaker consent, project entitlement, or voice likeness.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import os
import sys
import wave
from pathlib import Path

from google.genai import types

# Allow `python scripts/...` to import the application package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.live_session import create_genai_client  # noqa: E402
from app.config import settings  # noqa: E402
from app.voice.service import (  # noqa: E402
    MAX_WAV_BYTES,
    WavRecording,
    require_live_consent_acknowledgement,
    validate_wav,
)


def load_voice_wav(path: Path, *, minimum_seconds: float = 1.0) -> WavRecording:
    """Read bounded WAV input using the local validator, without uploading it."""
    try:
        with path.open("rb") as source:
            data = source.read(MAX_WAV_BYTES + 1)
    except OSError as exc:
        raise ValueError("Voice recording could not be read; check the configured path") from exc
    return validate_wav(data, label="Voice recording", minimum_seconds=minimum_seconds)


def prepare_reference(
    recording: WavRecording, seconds: int | None = None
) -> WavRecording:
    """Optionally select the first 10–20 seconds in memory; preserve the original."""
    if seconds is None:
        return recording
    if seconds not in range(10, 21) or seconds > recording.duration_seconds:
        raise ValueError("Reference selection must be 10–20 seconds within the recording")
    with wave.open(io.BytesIO(recording.data), "rb") as source:
        pcm = source.readframes(seconds * 24_000)
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(24_000)
        target.writeframes(pcm)
    return WavRecording(data=output.getvalue(), duration_seconds=float(seconds))


def build_replication_config(
    source_audio: bytes, consent_audio: bytes, *, wire_format: str = "sdk-wav"
) -> types.LiveConnectConfig:
    """Build one explicit protocol variant; this is not an entitlement check."""
    if wire_format == "cloud-pcm":
        recording = validate_wav(
            source_audio, label="Cloud voice sample", minimum_seconds=10
        )
        if recording.duration_seconds > 20:
            raise ValueError(
                "Cloud Live documents a 10–20 second sample; select a shorter reference"
            )
        with wave.open(io.BytesIO(recording.data), "rb") as source:
            sample_pcm = source.readframes(source.getnframes())
        # Follow the published Cloud example. Consent is checked by the operator;
        # this variant does not transmit the separately retained consent recording.
        replicated = types.ReplicatedVoiceConfig(
            mime_type="audio/pcm;rate=24000",
            voice_sample_audio=sample_pcm,
        )
    elif wire_format == "sdk-wav":
        replicated = types.ReplicatedVoiceConfig(
            mime_type="audio/wav",
            voice_sample_audio=source_audio,
            consent_audio=consent_audio,
        )
    else:
        raise ValueError("Unknown inline voice wire format")

    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                replicated_voice_config=replicated
            )
        ),
        system_instruction=(
            "This is a voice compatibility test. Reply in one short sentence."
        ),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )


def build_voice_id_config(voice: str) -> types.LiveConnectConfig:
    """Create a minimal Live config using a stored voice ID or ephemeral key."""
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(voice=voice)
        ),
        system_instruction=(
            "This is a voice compatibility test. Reply in one short sentence."
        ),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )


def create_ephemeral_voice_key(source_audio: bytes, consent_audio: bytes) -> str:
    """Create a seven-day, client-managed voice key for compatibility testing."""
    from google import genai

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    voice = client.voices.create(
        store=False,
        voice={
            "model": "gemini-3.8-flash-tts",
            "type": "replicated",
            "replicated": {
                "source_audio": {
                    "mime_type": "audio/wav",
                    "data": base64.b64encode(source_audio).decode("ascii"),
                },
                "consent_audio": {
                    "mime_type": "audio/wav",
                    "data": base64.b64encode(consent_audio).decode("ascii"),
                },
            },
        },
    )
    if not voice.key:
        raise RuntimeError("Gemini created a voice without returning a voice key")
    return voice.key


async def run_spike(
    source_path: Path,
    consent_path: Path,
    output_path: Path,
    prompt: str,
    mode: str,
    *,
    run_live: bool = False,
    confirm_consent: bool = False,
    reference_seconds: int | None = None,
    wire_format: str | None = None,
) -> None:
    if mode not in ("inline", "voice-key"):
        raise ValueError("Unknown voice test mode")
    if mode == "voice-key" and wire_format is not None:
        raise ValueError("Wire format applies only to inline mode")
    if wire_format not in (None, "sdk-wav", "cloud-pcm"):
        raise ValueError("Unknown inline voice wire format")
    if run_live and not confirm_consent:
        raise ValueError(
            "A live request sends recordings to Google and may incur charges. "
            "Explicit adult-speaker consent and --confirm-consent are required."
        )
    if run_live and mode == "inline" and wire_format is None:
        raise ValueError(
            "Choose --wire-format cloud-pcm or sdk-wav explicitly; provider contracts differ"
        )
    if output_path.resolve() in (source_path.resolve(), consent_path.resolve()):
        raise ValueError("Output must not replace the reference or consent recording")
    if output_path.exists():
        raise ValueError("Output already exists; choose a new path to preserve the prior result")

    original = load_voice_wav(source_path, minimum_seconds=10)
    source = prepare_reference(original, reference_seconds)
    consent = load_voice_wav(consent_path)

    print(
        "Local WAV validation passed (mono, PCM16, 24 kHz): "
        f"reference={original.duration_seconds:.2f}s, "
        f"selected={source.duration_seconds:.2f}s, "
        f"consent={consent.duration_seconds:.2f}s"
    )
    if reference_seconds is not None:
        print("Reference selection is in memory only; original recordings are unchanged.")
    if source.duration_seconds > 20:
        print("NOTE: Cloud Live documents a 10–20s reference; this reference exceeds 20s.")
    config = None
    if mode == "inline" and wire_format is not None:
        config = build_replication_config(
            source.data, consent.data, wire_format=wire_format
        )
        print(f"Prepared {wire_format} configuration locally; provider compatibility is unverified.")
    if not run_live:
        print("DRY RUN: no Google connection, voice enrollment, upload, or output file created.")
        print("Speaker consent, provider access, and voice likeness are NOT verified.")
        return

    print("LIVE TEST: sending authorized recording data to Google; usage charges may apply.")
    if mode == "voice-key":
        # This is the older, separate TTS experiment, not proof that Live accepts
        # TTS voice keys. It is never executed by a dry run.
        print("EXPERIMENTAL: creating a separate TTS voice key before the Live request.")
        voice_key = await asyncio.to_thread(
            create_ephemeral_voice_key, source.data, consent.data
        )
        config = build_voice_id_config(voice_key)

    if wire_format == "cloud-pcm":
        from google import genai

        # Do not silently route the Cloud sample through an AI Studio key.
        client = genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GOOGLE_CLOUD_LOCATION,
            http_options={"api_version": "v1alpha"},
        )
    else:
        client = create_genai_client()
    print(f"Connecting to {settings.ELARA_MODEL}...")

    pcm_chunks: list[bytes] = []
    transcript: list[str] = []
    # Bound the live portion of this one-sentence compatibility probe.
    async with asyncio.timeout(45), client.aio.live.connect(
        model=settings.ELARA_MODEL,
        config=config,
    ) as session:
        if mode == "inline" and wire_format == "sdk-wav":
            require_live_consent_acknowledgement(
                getattr(session, "setup_complete", None)
            )
            print(
                "Server acknowledged voice consent; speaker likeness is still unverified."
            )
        else:
            print(
                "Session connected; this path has no equivalent consent-signature "
                "gate. Voice replication is still unverified."
            )
        await session.send_client_content(
            turns=types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)],
            ),
            turn_complete=True,
        )
        async for response in session.receive():
            server_content = response.server_content
            if server_content is None:
                continue
            if server_content.model_turn:
                for part in server_content.model_turn.parts or []:
                    if part.inline_data and part.inline_data.data:
                        pcm_chunks.append(part.inline_data.data)
            if (
                server_content.output_transcription
                and server_content.output_transcription.text
            ):
                transcript.append(server_content.output_transcription.text)
            if server_content.turn_complete:
                break

    if not pcm_chunks:
        raise RuntimeError("Live session completed without returning audio")

    output_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # O_EXCL also protects against a file appearing after the preflight check.
    fd = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as destination:
        with wave.open(destination, "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(24_000)
            output.writeframes(b"".join(pcm_chunks))

    print(
        f"Received {sum(map(len, pcm_chunks))} PCM bytes. "
        "AUDIO RECEIVED ONLY — not a successful-cloning verdict. "
        "Manual speaker-likeness review is required."
    )
    print(f"Saved response to {output_path}")
    if transcript:
        print("Output transcription received (content intentionally not logged).")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, default=settings.ELARA_VOICE_REFERENCE_PATH)
    parser.add_argument("--consent", type=Path, default=settings.ELARA_VOICE_CONSENT_PATH)
    parser.add_argument(
        "--output",
        type=Path,
        default=settings.ELARA_VOICE_TEST_OUTPUT_PATH
        or Path(__file__).resolve().parents[1] / "Voice/converted/live-replication-new-result.wav",
    )
    parser.add_argument(
        "--prompt",
        default="Please say: I am Elara, an AI companion. How was your day?",
    )
    parser.add_argument(
        "--mode",
        choices=("inline", "voice-key"),
        default="inline",
        help="Test inline Live replication or a temporary Voices API key.",
    )
    parser.add_argument(
        "--reference-seconds", type=int, choices=range(10, 21), metavar="10..20",
        help="Use this many seconds from the beginning, in memory only.",
    )
    parser.add_argument(
        "--wire-format", choices=("sdk-wav", "cloud-pcm"),
        help="Explicit protocol variant; required for a live inline test.",
    )
    parser.add_argument(
        "--run-live", action="store_true",
        help="Opt in to Google requests and possible charges. Default is offline.",
    )
    parser.add_argument(
        "--confirm-consent", action="store_true",
        help="Confirm adult-speaker authorization and permission to send the selected audio.",
    )
    args = parser.parse_args(argv)
    if not args.sample or not args.consent:
        parser.error("Set both private voice paths in .env or supply --sample and --consent")
    return args


if __name__ == "__main__":
    arguments = parse_args()
    asyncio.run(
        run_spike(
            arguments.sample,
            arguments.consent,
            arguments.output,
            arguments.prompt,
            arguments.mode,
            run_live=arguments.run_live,
            confirm_consent=arguments.confirm_consent,
            reference_seconds=arguments.reference_seconds,
            wire_format=arguments.wire_format,
        )
    )
