import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.auth import AuthenticationError, authenticate_http_headers
from app.demo.models import (
    ClearBackground, CreateFamily, CreateRecipient, ReviewBackground,
    SelectRecipientVoice, SetWellbeingSharing,
)
from app.demo.service import get_demo_store, require_demo
from app.demo.store import DemoError
from app.voice.profiles import enrollment_available, get_voice_store
from app.voice.service import VoiceEnrollmentError

router = APIRouter(prefix="/api/demo", tags=["local-synthetic-demo"])


async def demo_identity(request: Request):
    try:
        require_demo(request.client.host if request.client else None,
                     request.headers.get("origin"), mutation=request.method != "GET")
        identity = await authenticate_http_headers(request.headers)
        if identity.provider != "development":
            raise DemoError("Only local demo identities are accepted.", 403)
        return identity.user_id
    except DemoError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    except AuthenticationError as exc:
        raise HTTPException(401, "Unable to verify demo browser identity.") from exc


async def execute(operation, *args):
    try:
        result = await asyncio.to_thread(operation, *args)
        return JSONResponse(result, headers={"Cache-Control": "no-store", "Vary": "X-Hugback-Development-User"})
    except DemoError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(503, "Local demo storage is unavailable; no cloud fallback was used.") from exc


@router.get("/family")
async def family(uid=Depends(demo_identity)):
    return await execute(get_demo_store().get, uid)


@router.post("/family")
async def create_family(payload: CreateFamily, uid=Depends(demo_identity)):
    return await execute(get_demo_store().create, uid, payload)


@router.put("/background")
async def review_background(payload: ReviewBackground, uid=Depends(demo_identity)):
    return await execute(get_demo_store().review, uid, payload)


@router.post("/background/clear")
async def clear_background(payload: ClearBackground, uid=Depends(demo_identity)):
    return await execute(get_demo_store().clear, uid, payload.recipientId, payload.revision)


@router.post("/recipients")
async def add_recipient(payload: CreateRecipient, uid=Depends(demo_identity)):
    return await execute(get_demo_store().add_recipient, uid, payload)


@router.put("/recipient-voice")
async def recipient_voice(payload: SelectRecipientVoice, uid=Depends(demo_identity)):
    if payload.mode == "child":
        if not enrollment_available():
            raise HTTPException(403, "Child voice is not available on this backend.")
        try:
            # Resolves owner, current profile, enabled status and expiry. No Google I/O.
            await asyncio.to_thread(get_voice_store().resolve, uid, payload.profileId)
        except VoiceEnrollmentError as exc:
            raise HTTPException(409, str(exc)) from exc
    return await execute(get_demo_store().select_voice, uid, payload)


@router.put("/wellbeing-sharing")
async def wellbeing_sharing(payload: SetWellbeingSharing, uid=Depends(demo_identity)):
    return await execute(get_demo_store().set_wellbeing_sharing, uid, payload)
