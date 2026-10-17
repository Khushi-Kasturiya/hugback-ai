import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.auth import AuthenticationError, authenticate_http_headers
from app.demo.models import (
    ClearBackground, CreateFamily, CreateRecipient, SetChildGender, ReviewBackground,
    SelectRecipientVoice, SetWellbeingSharing, SetToneContinuity, SetTranscriptSharing, SetAlertSharing,
    SetAlertDestination,
    GenerateLegacySummary,
)
from app.demo.service import get_demo_store, require_demo, require_demo_identity
from app.demo.store import DemoError
from app.demo.summary import summarize_call
from app.memory.models import TranscriptTurn
from app.memory.followup_service import contains_privacy_request
from app.wellbeing.service import contains_signal_privacy_request
from app.voice.profiles import enrollment_available, get_voice_store
from app.voice.service import VoiceEnrollmentError

router = APIRouter(prefix="/api/demo", tags=["local-synthetic-demo"])


async def demo_identity(request: Request):
    try:
        require_demo(request.client.host if request.client else None,
                     request.headers.get("origin"), mutation=request.method != "GET")
        identity = await authenticate_http_headers(request.headers)
        return require_demo_identity(identity)
    except DemoError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    except AuthenticationError as exc:
        raise HTTPException(401, "Unable to verify demo browser identity.") from exc


async def execute(operation, *args):
    try:
        result = await asyncio.to_thread(operation, *args)
        return JSONResponse(result, headers={"Cache-Control": "no-store", "Vary": "Authorization, X-Hugback-Development-User"})
    except DemoError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(503, "Synthetic test storage is unavailable. No alternate store was used.") from exc


@router.get("/family")
async def family(uid=Depends(demo_identity)):
    return await execute(get_demo_store().get, uid)


@router.post("/family")
async def create_family(payload: CreateFamily, uid=Depends(demo_identity)):
    return await execute(get_demo_store().create, uid, payload)


@router.put("/child-details")
async def child_details(payload: SetChildGender, uid=Depends(demo_identity)):
    return await execute(get_demo_store().set_child_gender, uid, payload)


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
            await asyncio.to_thread(lambda: get_voice_store().resolve(uid, payload.profileId))
        except VoiceEnrollmentError as exc:
            raise HTTPException(409, str(exc)) from exc
    return await execute(get_demo_store().select_voice, uid, payload)


@router.put("/wellbeing-sharing")
async def wellbeing_sharing(payload: SetWellbeingSharing, uid=Depends(demo_identity)):
    return await execute(get_demo_store().set_wellbeing_sharing, uid, payload)


@router.put("/tone-continuity")
async def tone_continuity(payload: SetToneContinuity, uid=Depends(demo_identity)):
    return await execute(get_demo_store().set_tone_continuity, uid, payload)


@router.put("/transcript-sharing")
async def transcript_sharing(payload: SetTranscriptSharing, uid=Depends(demo_identity)):
    return await execute(get_demo_store().set_transcript_sharing, uid, payload)


@router.put("/alert-sharing")
async def alert_sharing(payload: SetAlertSharing, uid=Depends(demo_identity)):
    return await execute(get_demo_store().set_alert_sharing, uid, payload)


@router.put("/alert-destination")
async def alert_destination(payload: SetAlertDestination, uid=Depends(demo_identity)):
    return await execute(get_demo_store().set_alert_destination, uid, payload)


@router.get("/summaries/{recipient_id}/{session_id}")
async def call_summary(recipient_id: str, session_id: str, uid=Depends(demo_identity)):
    if not recipient_id.startswith("demo-parent-") or not session_id.startswith("session-"):
        raise HTTPException(404, "No saved summary for this test call.")
    return await execute(get_demo_store().get_call_summary, uid, recipient_id, session_id)


@router.post("/summaries/{recipient_id}/{session_id}/generate")
async def generate_legacy_summary(recipient_id: str, session_id: str,
                                  payload: GenerateLegacySummary, uid=Depends(demo_identity)):
    if payload.recipientId != recipient_id or not session_id.startswith("session-"):
        raise HTTPException(404, "No older saved call can be summarized.")
    store = get_demo_store()
    try:
        data = await asyncio.to_thread(
            store.claim_legacy_summary, uid, recipient_id, payload.revision, session_id,
        )
    except DemoError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    try:
        turns = [TranscriptTurn(role=item["role"], text=item["text"], turn_index=index)
                 for index, item in enumerate(data["turns"])]
        if contains_privacy_request(turns) or contains_signal_privacy_request(turns):
            await asyncio.to_thread(store.revoke_transcript_sharing, recipient_id, data["generation"])
            return await execute(store.get, uid)
        if not await asyncio.to_thread(store.summary_eligible, recipient_id, session_id, data["generation"]):
            return await execute(store.get, uid)
        summary = await summarize_call(turns)
    except Exception:
        summary = None
    await asyncio.to_thread(store.finish_legacy_summary, uid, recipient_id, session_id,
                            data["generation"], summary)
    return await execute(store.get, uid)
