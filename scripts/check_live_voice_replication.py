#!/usr/bin/env python3
"""Compatibility spike for Gemini Live native voice replication.

This script deliberately stays outside the production request path. It verifies
that a consented 24 kHz WAV voice sample can be supplied through Live API's
ReplicatedVoiceConfig and writes one short response to a WAV file.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

from google.genai import types

# Allow `python scripts/...` to import the application package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.live_session import create_genai_client  # noqa: E402
from app.config import settings  # noqa: E402


@dataclass(frozen=True)
class WavRecording:
    data: bytes
    duration_seconds: float


def load_voice_wav(path: Path, *, minimum_seconds: float = 1.0) -> WavRecording:
    """Load and validate the exact WAV format required by Gemini Live."""
    try:
        with wave.open(str(path), "rb") as source:
            channels = source.getnchannels()
            sample_width = source.getsampwidth()
            frame_rate = source.getframerate()
            frame_count = source.getnframes()
    except (FileNotFoundError, wave.Error) as exc:
        raise ValueError(f"{path} is not a readable PCM WAV file") from exc

    if channels != 1:
        raise ValueError(f"{path} must be mono; found {channels} channels")
    if sample_width != 2:
        raise ValueError(f"{path} must use 16-bit PCM samples")
    if frame_rate != 24_000:
        raise ValueError(f"{path} must be 24 kHz; found {frame_rate} Hz")

    duration = frame_count / frame_rate
    if duration < minimum_seconds:
        raise ValueError(
            f"{path} is too short ({duration:.1f}s); need at least {minimum_seconds:.0f}s"
        )
    return WavRecording(data=path.read_bytes(), duration_seconds=duration)


def build_replication_config(
    source_audio: bytes, consent_audio: bytes
) -> types.LiveConnectConfig:
    """Create a minimal Live config using the SDK's native replication field."""
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                replicated_voice_config=types.ReplicatedVoiceConfig(
                    mime_type="audio/wav",
                    voice_sample_audio=source_audio,
                    consent_audio=consent_audio,
                )
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
) -> None:
    source = load_voice_wav(source_path, minimum_seconds=10)
    consent = load_voice_wav(consent_path)
    if mode == "voice-key":
        print("Creating an ephemeral Google-managed voice key...")
        voice_key = await asyncio.to_thread(
            create_ephemeral_voice_key,
            source.data,
            consent.data,
        )
        config = build_voice_id_config(voice_key)
        print("Voice key created (value intentionally not logged).")
    else:
        config = build_replication_config(source.data, consent.data)

    print(
        "Validated recordings: "
        f"sample={source.duration_seconds:.1f}s, consent={consent.duration_seconds:.1f}s"
    )
    print(f"Connecting to {settings.ELARA_MODEL}...")

    pcm_chunks: list[bytes] = []
    transcript: list[str] = []
    client = create_genai_client()
    async with client.aio.live.connect(
        model=settings.ELARA_MODEL,
        config=config,
    ) as session:
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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(24_000)
        output.writeframes(b"".join(pcm_chunks))

    print(f"PASS: received {sum(map(len, pcm_chunks))} PCM bytes")
    print(f"Saved response to {output_path}")
    if transcript:
        print(f"Transcript: {''.join(transcript).strip()}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--consent", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("voice-replication-spike.wav"),
    )
    parser.add_argument(
        "--prompt",
        default="Please say: Elara voice replication is working.",
    )
    parser.add_argument(
        "--mode",
        choices=("inline", "voice-key"),
        default="inline",
        help="Test inline Live replication or a temporary Voices API key.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    asyncio.run(
        run_spike(
            arguments.sample,
            arguments.consent,
            arguments.output,
            arguments.prompt,
            arguments.mode,
        )
    )
