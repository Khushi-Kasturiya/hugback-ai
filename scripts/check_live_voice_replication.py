#!/usr/bin/env python3
"""Verify the supported Voices API key -> Gemini Flash-Lite TTS flow."""

from __future__ import annotations

import argparse
import asyncio
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

# Allow `python scripts/...` to import the application package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.live_session import create_genai_client  # noqa: E402
from app.config import settings  # noqa: E402
from app.voice.service import (  # noqa: E402
    InlineVoice,
    create_replicated_voice_key,
    synthesize_replicated_speech,
)


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


def create_ephemeral_voice_key(source_audio: bytes, consent_audio: bytes) -> str:
    """Create a seven-day, client-managed voice key for compatibility testing."""
    return create_replicated_voice_key(
        create_genai_client(),
        InlineVoice(sample=source_audio, consent=consent_audio),
    )


async def run_spike(
    source_path: Path,
    consent_path: Path,
    output_path: Path,
    prompt: str,
) -> None:
    source = load_voice_wav(source_path, minimum_seconds=10)
    consent = load_voice_wav(consent_path)
    print("Creating an ephemeral Google-managed voice key...")
    voice_key = await asyncio.to_thread(
        create_ephemeral_voice_key,
        source.data,
        consent.data,
    )
    print("Voice key created (value intentionally not logged).")

    print(
        "Validated recordings: "
        f"sample={source.duration_seconds:.1f}s, consent={consent.duration_seconds:.1f}s"
    )
    print(f"Synthesizing with {settings.ELARA_TTS_MODEL}...")
    client = create_genai_client()
    audio = await synthesize_replicated_speech(
        client,
        voice_key=voice_key,
        text=prompt,
        model=settings.ELARA_TTS_MODEL,
    )
    if not audio.pcm:
        raise RuntimeError("TTS completed without returning audio")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(audio.sample_rate)
        output.writeframes(audio.pcm)

    print(f"PASS: received {len(audio.pcm)} PCM bytes")
    print(f"Saved response to {output_path}")


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
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    asyncio.run(
        run_spike(
            arguments.sample,
            arguments.consent,
            arguments.output,
            arguments.prompt,
        )
    )
