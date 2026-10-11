#!/usr/bin/env python3
"""Offline-first Voices API -> TTS probe, never Gemini Live.

Real requests require --run-live and --confirm-consent-and-billing. They upload
the recordings to Google and may charge the project owning GEMINI_API_KEY.
A client-managed voice key is kept in memory only; no saved voice is created.
This is not a zero-retention guarantee for all provider processing/logging.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
import os
from pathlib import Path
import re
import sys

from google import genai

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings  # noqa: E402
from app.voice.service import MAX_WAV_BYTES, validate_wav  # noqa: E402


DEFAULT_TEXT = (
    "Namaste, main Elara hoon, ek AI companion. Aaj aapka din kaisa raha?"
)
TTS_MODELS = ("gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts")


class ProbeError(ValueError):
    """Safe, local diagnostic text; do not include provider payloads or keys."""


def load_wav(path: Path, minimum_seconds: float) -> bytes:
    try:
        with path.open("rb") as source:
            data = source.read(MAX_WAV_BYTES + 1)
    except OSError:
        raise ProbeError("Cannot read a recording; check the private file paths.") from None
    return validate_wav(
        data, label="Recording", minimum_seconds=minimum_seconds
    ).data


def decode_output(interaction: object) -> bytes:
    if getattr(interaction, "status", None) != "completed":
        raise ProbeError("TTS did not complete; no audio saved and no automatic retry.")
    audio = getattr(interaction, "output_audio", None)
    if getattr(audio, "mime_type", None) not in ("audio/wav", "audio/x-wav"):
        raise ProbeError("Expected inline WAV output; no format or URL fallback attempted.")
    data = getattr(audio, "data", None)
    if not isinstance(data, str) or not data or len(data) > 4 * ((MAX_WAV_BYTES + 2) // 3):
        raise ProbeError("TTS returned missing or oversized inline audio.")
    try:
        decoded = base64.b64decode(data, validate=True)
    except (ValueError, binascii.Error):
        raise ProbeError("TTS returned invalid base64 audio.") from None
    # The diagnostic intentionally accepts only a short, correctly labelled WAV,
    # rather than guessing a rate or wrapping MP3/PCM bytes in a WAV header.
    return validate_wav(
        decoded, label="TTS output", minimum_seconds=0.1
    ).data


def save_new_output(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
    ) as target:
        target.write(data)


def create_tts_client(api_key: str, *, transport=None):
    sent: set[tuple[str, str]] = set()

    async def send_once(request) -> None:
        route = (request.method, request.url.path)
        if route in sent:
            raise ProbeError(
                "A repeated API transmission was blocked; no automatic retry is allowed."
            )
        sent.add(route)

    # SDK 2.28 normalizes attempts=0 to 1, while its Voices bridge interprets
    # that as one retry. Enforce the one-send limit at the HTTP request boundary
    # as well. The transport override is only for synthetic offline tests.
    client_args = {"event_hooks": {"request": [send_once]}}
    if transport is not None:
        client_args["transport"] = transport
    return genai.Client(
        api_key=api_key,
        vertexai=False,
        http_options={
            "api_version": "v1beta",
            "timeout": 45_000,
            "retry_options": {"attempts": 0},
            "async_client_args": client_args,
        },
    )


async def run_probe(
    sample: Path,
    consent: Path,
    output: Path,
    *,
    text: str = DEFAULT_TEXT,
    model: str = TTS_MODELS[0],
    run_live: bool = False,
    confirm_consent_and_billing: bool = False,
) -> None:
    if run_live and not confirm_consent_and_billing:
        raise ProbeError(
            "Live use requires --confirm-consent-and-billing: authorize adult-speaker "
            "recording uploads and charges to the API-key owner's project."
        )
    if model not in TTS_MODELS:
        raise ProbeError("Select a supported TTS model, not a Live model.")
    if not text.strip() or len(text) > 280:
        raise ProbeError("Use a short test sentence of 1–280 characters.")
    if output.resolve() in (sample.resolve(), consent.resolve()):
        raise ProbeError("Output must not replace an input recording.")
    if output.exists() or output.is_symlink():
        raise ProbeError("Output already exists; choose a new filename.")

    reference = load_wav(sample, minimum_seconds=10)
    consent_bytes = load_wav(consent, minimum_seconds=1)
    print("Local validation passed: reference and consent are mono PCM16 24kHz WAV.")
    if not run_live:
        print(
            "DRY RUN: no API client, upload, voice creation, synthesis or output file. "
            "Billing, consent contents, account access and voice likeness are unverified."
        )
        return
    if not settings.GEMINI_API_KEY:
        raise ProbeError("GEMINI_API_KEY is required; no Vertex/ADC fallback is allowed.")

    client = create_tts_client(settings.GEMINI_API_KEY)
    try:
        async with asyncio.timeout(90):
            print("Uploading authorized recordings to the Voices API (store=False).")
            voice = await client.aio.voices.create(
                store=False,
                voice={
                    "model": model,
                    "type": "replicated",
                    "replicated": {
                        "source_audio": {
                            "mime_type": "audio/wav",
                            "data": base64.b64encode(reference).decode("ascii"),
                        },
                        "consent_audio": {
                            "mime_type": "audio/wav",
                            "data": base64.b64encode(consent_bytes).decode("ascii"),
                        },
                    },
                },
            )
            voice_key = getattr(voice, "key", None)
            if (
                not isinstance(voice_key, str)
                or not voice_key.startswith("voicekey_")
                or not voice_key.removeprefix("voicekey_").strip()
            ):
                raise ProbeError(
                    "No client-managed replicated-voice key returned. "
                    "Stopped without requesting speech or falling back to a preset."
                )
            print("Temporary replicated-voice key received; requesting one TTS preview.")
            result = await client.aio.interactions.create(
                model=model,
                store=False,
                input=[{
                    "type": "user_input",
                    "content": [{
                        "type": "text",
                        "text": text,
                        "annotations": [{
                            "type": "speech_metadata",
                            "style": "warm and conversational",
                        }],
                    }],
                }],
                response_format={"type": "audio"},
                generation_config={"speech_config": [{"voice": voice_key}]},
            )
            data = decode_output(result)
    finally:
        await client.aio.aclose()
        client.close()

    save_new_output(output, data)
    print(f"TTS preview saved to {output}")
    print("Not a cloning-success verdict: the speaker must review likeness.")
    print("No voice key persisted; normal Elara conversations are unchanged.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, default=settings.ELARA_VOICE_REFERENCE_PATH)
    parser.add_argument("--consent", type=Path, default=settings.ELARA_VOICE_CONSENT_PATH)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--model", choices=TTS_MODELS, default=TTS_MODELS[0])
    parser.add_argument("--run-live", action="store_true")
    parser.add_argument("--confirm-consent-and-billing", action="store_true")
    args = parser.parse_args(argv)
    if not args.sample or not args.consent:
        parser.error("Supply both recordings or configure their private paths in .env.")
    return args


def redact_provider_message(message: str) -> str:
    """Expose a short diagnostic, not echoed credentials, recordings or URLs."""
    if settings.GEMINI_API_KEY:
        message = message.replace(settings.GEMINI_API_KEY, "[REDACTED API KEY]")
    message = re.sub(r"AIza[A-Za-z0-9_-]{20,}", "[REDACTED API KEY]", message)
    message = re.sub(r"voicekey_[A-Za-z0-9_-]+", "[REDACTED VOICE KEY]", message)
    message = re.sub(r"(?i)Bearer\s+\S+", "[REDACTED TOKEN]", message)
    message = re.sub(r"https?://[^\s<>]+", "[REDACTED URL]", message)
    message = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED EMAIL]", message)
    message = re.sub(r"/(?:Users|private|tmp)/[^\s\"'`]+", "[REDACTED PATH]", message)
    message = re.sub(r"[A-Za-z0-9+/=_-]{64,}", "[REDACTED DATA]", message)
    # Provider diagnostics can quote user-supplied text or field values.
    message = re.sub(r'(["`]).*?\1', "[REDACTED VALUE]", message, flags=re.DOTALL)
    return " ".join(message.split())[:500]


def safe_error_message(error: Exception) -> str:
    # Never print the exception, request, complete response body, or ErrorInfo
    # metadata. Read only the provider's designated diagnostic message.
    if isinstance(error, ProbeError):
        return str(error)
    code = getattr(error, "code", None) or getattr(error, "status_code", None)
    if isinstance(code, int):
        summary = f"Provider HTTP {code}; stopped without retry or fallback."
        # The SDK's Voices/Interactions bridge uses .body; older APIs use .details.
        for attribute in ("body", "details"):
            body = getattr(error, attribute, None)
            if not isinstance(body, dict):
                continue
            payload = body.get("error", body)
            if not isinstance(payload, dict):
                continue
            message = payload.get("message")
            if isinstance(message, str) and message.strip():
                return f"{summary}\nGoogle: {redact_provider_message(message)}"
        return f"{summary} No structured provider reason was available."
    return (
        "Probe stopped: local format, network, timeout or provider failure. "
        "Private error details were suppressed; no automatic retry."
    )


if __name__ == "__main__":
    arguments = parse_args()
    try:
        asyncio.run(run_probe(
            arguments.sample, arguments.consent, arguments.output,
            text=arguments.text, model=arguments.model,
            run_live=arguments.run_live,
            confirm_consent_and_billing=arguments.confirm_consent_and_billing,
        ))
    except Exception as error:
        print(safe_error_message(error), file=sys.stderr)
        raise SystemExit(1) from None
