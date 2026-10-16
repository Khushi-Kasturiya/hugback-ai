import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.auth import AuthenticationError, UserIdentity, authenticate_http_headers
from app.config import settings
from app.portal.service import read_shared_summaries
from app.demo.service import enabled as demo_enabled, require_demo, require_demo_identity
from app.demo.store import DemoError
from app.voice.profiles import enrollment_available, get_voice_store, voice_owner

router = APIRouter(prefix="/api/portal", tags=["child-portal"])


async def portal_identity(request: Request, response: Response) -> UserIdentity:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Authorization, X-Hugback-Development-User"
    if settings.HUGBACK_AUTH_MODE.lower() == "development":
        # Never trust X-Forwarded-For. This only enables the local development
        # interface; even localhost callers never receive private cloud records.
        if not request.client or request.client.host not in {"127.0.0.1", "::1"}:
            raise HTTPException(403, "Development portal is localhost-only")
    try:
        identity = await authenticate_http_headers(request.headers)
        if settings.HUGBACK_DEMO_STORE == "firestore":
            require_demo(request.client.host if request.client else None, request.headers.get("origin"),
                         mutation=False)
            require_demo_identity(identity)
        return identity
    except AuthenticationError as exc:
        raise HTTPException(401, "Unable to verify portal identity") from exc
    except DemoError as exc:
        raise HTTPException(exc.status, str(exc)) from exc


def sharing_gate(identity: UserIdentity) -> str:
    if settings.HUGBACK_DEMO_STORE == "firestore":
        return "synthetic_test_only"
    if identity.provider != "firebase":
        return "development_only"
    if not settings.PORTAL_SHARING_ENABLED or not settings.FIRESTORE_ENABLED:
        return "not_configured"
    return "awaiting_parent_link"


@router.get("/status")
async def portal_status(identity: UserIdentity = Depends(portal_identity)):
    profile = None
    if (identity.provider == "development" or demo_enabled()) and settings.HUGBACK_VOICE_DB_PATH.exists():
        try:
            profile = await asyncio.to_thread(get_voice_store().get, voice_owner(identity))
        except Exception as exc:
            raise HTTPException(503, "Voice selection is unavailable; call setup is blocked.") from exc
    return {
        "identityMode": identity.provider,
        "voice": {
            "mode": settings.HUGBACK_LIVE_VOICE_MODE, "name": settings.HUGBACK_VOICE_NAME,
            "replicatedTtsEnabled": enrollment_available(),
            "profile": profile,
        },
        "sharingStatus": sharing_gate(identity),
        "importsStatus": "local_preview_only",
        "localDemoEnabled": demo_enabled(),
        "demoStorage": settings.HUGBACK_DEMO_STORE,
        "canonicalStateStore": "firestore",
        "selectedStateAdapter": (
            "firestore" if settings.HUGBACK_DEMO_STORE == "firestore" else "sqlite_test_adapter"
        ),
        "browserDraftStore": "indexeddb_private_preconsent_staging",
        "workflowEnabled": settings.HUGBACK_WORKFLOW_ENABLED,
    }


@router.get("/summaries")
async def portal_summaries(identity: UserIdentity = Depends(portal_identity)):
    gate = sharing_gate(identity)
    if gate != "awaiting_parent_link":
        return {"status": gate, "summaries": []}
    try:
        return await read_shared_summaries(identity.user_id)
    except Exception as exc:
        # Do not log private mailbox content or claim an unavailable read is empty.
        raise HTTPException(503, "Approved summaries are temporarily unavailable") from exc
