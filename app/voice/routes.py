"""Explicit, bounded enrollment. No automatic uploads or paid retries."""

import asyncio
import base64
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from google import genai
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.auth import AuthenticationError, authenticate_http_headers
from app.config import settings
from app.voice.profiles import enrollment_available, get_voice_store, require_voice_access, voice_owner
from app.auth import UserIdentity
from app.voice.service import MAX_BASE64_CHARS, VoiceEnrollmentError, parse_inline_voice

router = APIRouter(prefix="/api/voice", tags=["voice"])
logger = logging.getLogger("hugback.voice")
_enrolling: set[str] = set()  # Local single-worker server, not a distributed lock.


class VoiceProvisionFailure(Exception):
    """A content-free record of the first enrollment transport failure."""

    def __init__(self, *, status_code: int | None = None, repeated_send: bool = False):
        self.status_code = status_code
        self.repeated_send = repeated_send
        super().__init__("voice enrollment transport failed")


def provision_failure_detail(exc: Exception) -> str:
    suffix = " No automatic retry was made. Refresh voice status before trying again."
    if isinstance(exc, VoiceProvisionFailure):
        if exc.repeated_send:
            return "A second voice upload was blocked; the first request's outcome is unknown." + suffix
        if exc.status_code in (401, 403):
            return f"Google rejected voice setup (HTTP {exc.status_code}). Check the backend API key's project access and voice feature eligibility." + suffix
        if exc.status_code == 429:
            return "Google limited voice setup (HTTP 429). Check the backend API key project's quota and billing." + suffix
        if exc.status_code is not None and 400 <= exc.status_code < 500:
            return f"Google rejected voice setup (HTTP {exc.status_code}). Check recording and consent requirements, and project access." + suffix
        if exc.status_code is not None and 500 <= exc.status_code < 600:
            return f"Google voice setup is unavailable (HTTP {exc.status_code})." + suffix
    return "Voice setup did not complete; the cause could not be determined safely." + suffix


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
    response.headers["Vary"] = "Authorization, X-Hugback-Development-User"
    try:
        require_voice_access(
            request.client.host if request.client else None, request.headers.get("origin"),
            mutation=request.method != "GET",
        )
        identity = await authenticate_http_headers(request.headers)
        return UserIdentity(user_id=voice_owner(identity), provider=identity.provider)
    except AuthenticationError as exc:
        raise HTTPException(401, "Unable to verify browser identity") from exc
    except VoiceEnrollmentError as exc:
        raise HTTPException(403, str(exc)) from exc


async def provision_voice(recordings):
    sent = False

    async def send_once(request):
        nonlocal sent
        if sent:
            raise VoiceProvisionFailure(repeated_send=True)
        sent = True

    async def capture_first_error(response):
        # Stop the SDK's retry layer before it can hide the first Google status.
        # Never read or log the response body, which can contain private data.
        if response.status_code >= 400:
            raise VoiceProvisionFailure(status_code=response.status_code)

    client = genai.Client(
        api_key=settings.GEMINI_API_KEY, vertexai=False,
        http_options={"api_version": "v1beta", "timeout": 45_000,
                      "retry_options": {"attempts": 0},
                      "async_client_args": {"event_hooks": {
                          "request": [send_once], "response": [capture_first_error],
                      }}},
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
    try:
        def read():
            store = get_voice_store()
            if settings.HUGBACK_DEMO_STORE == "firestore":
                return store.status(identity.user_id)
            return {"profile": store.get(identity.user_id), "enrolling": identity.user_id in _enrolling}
        return await asyncio.to_thread(read)
    except Exception as exc:
        raise HTTPException(503, "Voice storage is unavailable. No local fallback was used.") from exc


@router.post("/enroll")
async def enroll_voice(payload: VoiceEnrollmentRequest, identity=Depends(voice_identity)):
    if not enrollment_available():
        raise HTTPException(403, "Replicated TTS enrollment is not enabled for this backend.")
    cloud = settings.HUGBACK_DEMO_STORE == "firestore"
    if not cloud and _enrolling:
        raise HTTPException(409, "Voice setup is already processing. Refresh its status before retrying.")
    try:
        recordings = parse_inline_voice(payload.model_dump())
    except VoiceEnrollmentError as exc:
        raise HTTPException(400, str(exc)) from exc
    token = None
    try:
        store = await asyncio.to_thread(get_voice_store)
        if cloud:
            token = await asyncio.to_thread(store.begin_enrollment, identity.user_id)
        else:
            _enrolling.add(identity.user_id)
    except VoiceEnrollmentError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(503, "Voice storage is unavailable. No recordings were sent to Google.") from exc
    try:
        try:
            voice = await provision_voice(recordings)
        except Exception as exc:
            # Neither provider errors nor validation messages may echo keys/audio.
            logger.warning("Voice provider request failed (%s, HTTP %s)",
                           type(exc).__name__, getattr(exc, "status_code", None))
            raise HTTPException(502, provision_failure_detail(exc)) from exc
        try:
            profile = await asyncio.to_thread(
                store.save, identity.user_id, voice.key, getattr(voice, "expire_time", None),
                **({"enrollment_token": token} if cloud else {}),
            )
        except Exception as exc:
            logger.warning("Voice provider response could not be saved (%s)", type(exc).__name__)
            location = "Firestore" if cloud else "local"
            raise HTTPException(500, f"Google returned a voice, but {location} voice setup could not save it. "
                                "Refresh voice status and check backend storage before another upload.") from exc
        return {"profile": profile}
    finally:
        if cloud:
            try:
                await asyncio.to_thread(store.end_enrollment, identity.user_id, token)
            except Exception as exc:
                # A failed release expires automatically; never retry Google or
                # let cleanup turn a successful saved profile into a failure.
                logger.warning("Voice enrollment lease release unavailable (%s)", type(exc).__name__)
        else:
            _enrolling.discard(identity.user_id)


@router.put("/profile")
async def select_voice(payload: VoiceSelectionRequest, identity=Depends(voice_identity)):
    if settings.HUGBACK_DEMO_STORE != "firestore" and identity.user_id in _enrolling:
        raise HTTPException(409, "Wait for voice setup to finish.")
    if payload.enabled and not enrollment_available():
        raise HTTPException(403, "Custom voice is disabled on this backend.")
    try:
        def select():
            return get_voice_store().select(identity.user_id, payload.profileId, payload.enabled)
        return {"profile": await asyncio.to_thread(select)}
    except VoiceEnrollmentError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(503, "Voice storage is unavailable. Refresh voice status.") from exc


@router.delete("/profile")
async def delete_voice(identity=Depends(voice_identity)):
    if settings.HUGBACK_DEMO_STORE != "firestore" and identity.user_id in _enrolling:
        raise HTTPException(409, "Wait for voice setup to finish before removing it.")
    try:
        await asyncio.to_thread(lambda: get_voice_store().delete(identity.user_id))
    except VoiceEnrollmentError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(503, "Voice removal could not be confirmed. Refresh voice status.") from exc
    return {"profile": None}
