"""Explicit, bounded local enrollment. No automatic uploads or paid retries."""

import asyncio
import base64
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from google import genai
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.auth import AuthenticationError, authenticate_http_headers
from app.config import settings
from app.voice.profiles import enrollment_available, get_voice_store, require_local_voice
from app.voice.service import MAX_BASE64_CHARS, VoiceEnrollmentError, parse_inline_voice

router = APIRouter(prefix="/api/voice", tags=["voice"])
logger = logging.getLogger("elara.voice")
_enrolling: set[str] = set()  # Local single-worker server, not a distributed lock.


class VoiceEnrollmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    voiceSampleAudio: str = Field(min_length=1, max_length=MAX_BASE64_CHARS, repr=False)
    consentAudio: str = Field(min_length=1, max_length=MAX_BASE64_CHARS, repr=False)
    adultOwnVoice: Literal[True]
    consentToGoogleAndBilling: Literal[True]


class VoiceSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profileId: str = Field(pattern=r"^[a-f0-9]{32}$")
    enabled: StrictBool


async def voice_identity(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Authorization, X-Elara-Development-User"
    try:
        require_local_voice(
            request.client.host if request.client else None, request.headers.get("origin"),
            mutation=request.method != "GET",
        )
        return await authenticate_http_headers(request.headers)
    except AuthenticationError as exc:
        raise HTTPException(401, "Unable to verify browser identity") from exc
    except VoiceEnrollmentError as exc:
        raise HTTPException(403, str(exc)) from exc


async def provision_voice(recordings):
    sent = False

    async def send_once(request):
        nonlocal sent
        if sent:
            raise RuntimeError("Automatic voice-enrollment retry blocked")
        sent = True

    client = genai.Client(
        api_key=settings.GEMINI_API_KEY, vertexai=False,
        http_options={"api_version": "v1beta", "timeout": 45_000,
                      "retry_options": {"attempts": 0},
                      "async_client_args": {"event_hooks": {"request": [send_once]}}},
    )
    try:
        async with asyncio.timeout(55):
            # Deliberately omit model: preserve the friend's working enrollment route.
            return await client.aio.voices.create(store=False, voice={
                "type": "replicated",
                "replicated": {
                    "source_audio": {"mime_type": "audio/wav", "data": base64.b64encode(recordings.sample).decode("ascii")},
                    "consent_audio": {"mime_type": "audio/wav", "data": base64.b64encode(recordings.consent).decode("ascii")},
                },
            })
    finally:
        await client.aio.aclose()
        client.close()


@router.get("/profile")
async def voice_profile(identity=Depends(voice_identity)):
    return {"profile": await asyncio.to_thread(get_voice_store().get, identity.user_id),
            "enrolling": identity.user_id in _enrolling}


@router.post("/enroll")
async def enroll_voice(payload: VoiceEnrollmentRequest, identity=Depends(voice_identity)):
    if not enrollment_available():
        raise HTTPException(403, "Replicated TTS enrollment is not enabled for this local backend.")
    if _enrolling:
        raise HTTPException(409, "Voice setup is already processing. Refresh its status before retrying.")
    try:
        recordings = parse_inline_voice(payload.model_dump())
    except VoiceEnrollmentError as exc:
        raise HTTPException(400, str(exc)) from exc
    _enrolling.add(identity.user_id)
    try:
        voice = await provision_voice(recordings)
        profile = await asyncio.to_thread(
            get_voice_store().save, identity.user_id, voice.key, getattr(voice, "expire_time", None),
        )
        return {"profile": profile}
    except Exception as exc:
        # Neither API errors nor validation messages may echo provider keys/audio.
        logger.warning("Voice enrollment failed (%s)", type(exc).__name__)
        detail = (
            "Google did not complete voice setup. Check project access, billing and recordings. "
            "No automatic retry was made. Refresh voice status before trying again."
        )
        if "Paid Quota Tier 1" in str(exc):
            detail = "Google requires Paid Tier 1 on the backend API key's project. Check that project's billing."
        raise HTTPException(502, detail) from exc
    finally:
        _enrolling.discard(identity.user_id)


@router.put("/profile")
async def select_voice(payload: VoiceSelectionRequest, identity=Depends(voice_identity)):
    if identity.user_id in _enrolling:
        raise HTTPException(409, "Wait for voice setup to finish.")
    if payload.enabled and not enrollment_available():
        raise HTTPException(403, "Custom voice is disabled on this backend.")
    try:
        return {"profile": await asyncio.to_thread(
            get_voice_store().select, identity.user_id, payload.profileId, payload.enabled,
        )}
    except VoiceEnrollmentError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.delete("/profile")
async def delete_voice(identity=Depends(voice_identity)):
    if identity.user_id in _enrolling:
        raise HTTPException(409, "Wait for voice setup to finish before removing it.")
    await asyncio.to_thread(get_voice_store().delete, identity.user_id)
    return {"profile": None}
