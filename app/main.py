"""FastAPI application for Hugback's authenticated live-audio WebSocket broker.

Uses official Google GenAI SDK (google-genai) with direct support for both
Google AI Studio GEMINI_API_KEY and Vertex AI Application Default Credentials.
"""

import asyncio
import base64
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse
from google.genai import errors as genai_errors, types

from app.agent.live_session import create_genai_client, create_live_config
from app.voice.grammar import speaking_form_for_call
from app.auth import (
    AuthenticationError,
    authenticate_http_headers,
    authenticate_message,
)
from app.config import settings
from app.memory.models import ProcessMemoryRequest
from app.memory.processor import (
    dispatch_memory_processing,
    process_session_memory,
    task_request_is_authorized,
)
from app.memory.service import DisabledMemoryService, get_memory_service, render_memory_context
from app.memory.followups import context_card
from app.memory.followup_service import contains_privacy_request, get_followup_coordinator
from app.memory.store import get_session_store
from app.memory.transcript import TranscriptCollector, merge_transcription
from app.memory.failures import memory_error_code
from app.portal.routes import router as portal_router
from app.demo.routes import router as demo_router
from app.demo.service import background_context, get_demo_coordinator, get_demo_store, require_demo, require_demo_identity
from app.workflows.planner import prepare_call, plan_context
from app.workflows.critic import finish_quality_review
from app.workflows.contracts import ToolOutcome
from app.demo.store import DemoError
from app.demo.summary import summarize_call, summary_input
from app.alerts.policy import asks_not_to_alert, detect_topic
from app.alerts.email import configured as alert_email_configured, send_test_notice
from app.wellbeing.service import (
    SIGNAL_CONTEXT,
    TONE_SIGNAL_CONTEXT,
    SignalCollector,
    contains_signal_privacy_request,
    contains_tone_privacy_request,
    tone_context,
)
from app.voice.service import (
    VoiceConsentError,
    VoiceEnrollmentError,
    parse_call_voice,
    require_live_consent_acknowledgement,
    split_ready_speech,
)

from app.voice.routes import router as voice_router
from app.voice.profiles import enrollment_available, get_voice_store, require_local_voice, voice_owner
from app.voice.playback import ReplicatedPlayback


def live_failure_detail(exc: Exception, *, connected: bool) -> tuple[int | None, str]:
    """Return only the provider status category, never its response body."""
    code = exc.code if isinstance(exc, genai_errors.APIError) and isinstance(exc.code, int) else None
    prefix = "The voice connection stopped" if connected else "Google did not open the voice connection"
    if code == 400:
        return code, f"{prefix} (HTTP 400). The Live call setup was rejected; check its model and settings."
    if code in (401, 403):
        return code, f"{prefix} (HTTP {code}). Check the backend API key's project and Live model access."
    if code == 404:
        return code, f"{prefix} (HTTP 404). Check whether this Live model is available to the backend API key."
    if code == 429:
        return code, f"{prefix} (HTTP 429). The project may be at its Live quota or capacity limit; check usage before retrying."
    if code is not None and 500 <= code < 600:
        return code, f"{prefix} (HTTP {code}). Google Live was unavailable; try again later."
    if code == 1011:
        return code, (f"{prefix} (WebSocket 1011). Google closed Live setup, but this code does not identify why. "
                      "Check this API key's Live limits and status in Google AI Studio; compare a Stream test in the same project.")
    if code == 1006:
        return code, (f"{prefix} (WebSocket 1006). The connection ended without a provider close reason. "
                      "Check network or VPN connectivity before another attempt.")
    return code, f"{prefix}. The provider reason could not be classified safely. Check the backend's Live configuration."

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("hugback.broker")
# Strong references keep bounded local finalizers alive when a browser closes
# its ASGI/WebSocket task. This is not a durable queue across server shutdown.
_demo_finalizers: set[asyncio.Task] = set()

# Initialize FastAPI
@asynccontextmanager
async def lifespan(app):
    settings.validate_test_mode()
    yield


app = FastAPI(
    title="Hugback Multimodal Live Audio Broker",
    version="0.1.0",
    description="Bidirectional low-latency audio broker connecting to Gemini Multimodal Live API",
    lifespan=lifespan,
)

# CORS Middleware for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(portal_router)
app.include_router(demo_router)
app.include_router(voice_router)


@app.exception_handler(RequestValidationError)
async def private_validation_errors(request: Request, exc: RequestValidationError):
    if request.url.path.startswith("/api/voice/"):
        # FastAPI's default validation response can echo rejected audio input.
        return JSONResponse(
            status_code=422, headers={"Cache-Control": "no-store"},
            content={"detail": "Invalid voice request. Both bounded recordings and explicit consent are required."},
        )
    return await request_validation_exception_handler(request, exc)


@app.get("/healthz")
async def healthz():
    """Health check endpoint."""
    auth_mode = "api_key" if settings.GEMINI_API_KEY else "vertex_ai"
    memory_service = (
        DisabledMemoryService("canonical follow-up mode")
        if settings.FOLLOWUPS_ENABLED else get_memory_service()
    )
    from app.memory.store import DisabledSessionStore
    session_store = DisabledSessionStore("synthetic test uses its own repository") if settings.LOCAL_DEMO_ENABLED else get_session_store()
    return {
        "status": "healthy",
        "auth_mode": auth_mode,
        "has_api_key": bool(settings.GEMINI_API_KEY),
        "project": settings.GOOGLE_CLOUD_PROJECT,
        "location": settings.GOOGLE_CLOUD_LOCATION,
        "model": settings.HUGBACK_MODEL,
        "voice": settings.HUGBACK_VOICE_NAME,
        "voice_mode": settings.HUGBACK_LIVE_VOICE_MODE,
        "caller_auth": settings.HUGBACK_AUTH_MODE,
        "memory_configured": settings.MEMORY_ENABLED,
        "memory_operational": memory_service.enabled,
        "memory_error": getattr(memory_service, "reason", None),
        "firestore_configured": settings.FIRESTORE_ENABLED,
        "firestore_operational": session_store.enabled,
        "firestore_error": getattr(session_store, "reason", None),
        "memory_processing": settings.MEMORY_PROCESSING_MODE,
        "followups_configured": settings.FOLLOWUPS_ENABLED,
        "demo_storage": settings.HUGBACK_DEMO_STORE,
        "workflow_enabled": settings.HUGBACK_WORKFLOW_ENABLED,
        "demo_storage_verified": False,  # Configuration is not a successful database probe.
    }


@app.post("/internal/memory/process")
async def memory_process_endpoint(payload: ProcessMemoryRequest, request: Request):
    """Cloud Tasks target for retryable, post-call memory consolidation."""
    if settings.HUGBACK_DEMO_STORE == "firestore":
        raise HTTPException(403, "Legacy memory processing is disabled in synthetic cloud tests")
    if not await asyncio.to_thread(task_request_is_authorized, request.headers):
        raise HTTPException(status_code=403, detail="Unauthorized task request")
    try:
        status = await process_session_memory(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": status}


@app.get("/api/memories")
async def inspect_memories(request: Request):
    """Return exactly what the authenticated user is currently remembered as."""
    if settings.HUGBACK_DEMO_STORE == "firestore":
        raise HTTPException(403, "Production memory APIs are disabled in synthetic cloud tests")
    try:
        identity = await authenticate_http_headers(request.headers)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if settings.FOLLOWUPS_ENABLED:
        try:
            followups = get_followup_coordinator()
            return await followups.inspect(identity.user_id)
        except Exception:
            raise HTTPException(status_code=503, detail="Follow-up storage is unavailable")
    context = await get_memory_service().inspect(identity.user_id)
    return {"profiles": context.profiles, "facts": context.facts}


@app.delete("/api/memories")
async def delete_memories(request: Request):
    """Delete Memory Bank facts/profiles and persisted transcripts for one user."""
    if settings.HUGBACK_DEMO_STORE == "firestore":
        raise HTTPException(403, "Production memory APIs are disabled in synthetic cloud tests")
    try:
        identity = await authenticate_http_headers(request.headers)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    # Tombstone first. Old in-flight calls must not recreate deleted memories.
    try:
        followups = get_followup_coordinator(privacy_operation=True)
        if followups:
            await followups.delete_all(identity.user_id)
    except Exception:
        raise HTTPException(status_code=503, detail="Unable to confirm memory deletion")
    await get_memory_service().delete_all(identity.user_id)
    await get_session_store().delete_user_data(identity.user_id)
    return {"status": "deleted"}


def get_client_ip(ws: WebSocket) -> str:
    """Extract client IP."""
    xff = ws.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return ws.client.host if ws.client else "unknown"


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for bidirectional audio streaming with Gemini Live API."""
    client_ip = get_client_ip(websocket)
    session_id = f"session-{uuid.uuid4().hex}"
    started_at = datetime.now(timezone.utc)
    collector = TranscriptCollector()
    user_id: str | None = None
    voice_key = None
    inline_voice = None
    followups = None
    followup_plan = None
    demo_state = None
    demo_store = None
    call_ready = False
    speaking_form = "feminine"
    signal_collector = SignalCollector(enabled=False)
    signal_generation = 0
    tone_generation = 0
    transcript_generation = 0
    alert_generation = 0
    conversation_plan = None
    workflow_active = False
    tool_outcomes = []

    logger.info(f"Incoming WebSocket connection from {client_ip} [session: {session_id}]")
    await websocket.accept()

    try:
        authentication_text = await asyncio.wait_for(websocket.receive_text(), timeout=15)
        authentication_message = json.loads(authentication_text)
        identity = await authenticate_message(authentication_message)
        if ("demoRecipientId" in authentication_message or "demoRecipientRevision" in authentication_message) and authentication_message.get("demoParent") is not True:
            raise DemoError("Recipient selection is supported only in the local parent simulator.", 400)
        if settings.HUGBACK_DEMO_STORE == "firestore" and authentication_message.get("demoParent") is not True:
            raise DemoError("Cloud test mode accepts only explicitly selected synthetic recipients.", 403)
        inline_voice = parse_call_voice(authentication_message)
        if inline_voice:
            speaking_form = "neutral"  # Experimental inline audio has no child setup detail.
        if "voiceKey" in authentication_message:
            raise VoiceEnrollmentError("Use an owner-scoped portal voice profile, not a provider key.")
        if "voiceProfileId" in authentication_message:
            if not enrollment_available() or inline_voice:
                raise VoiceEnrollmentError("Replicated TTS is unavailable for this call")
            require_local_voice(
                websocket.client.host if websocket.client else None,
                websocket.headers.get("origin"),
            )
            voice_key = await asyncio.to_thread(
                get_voice_store().resolve, voice_owner(identity),
                authentication_message["voiceProfileId"],
            )
            speaking_form = "neutral"  # No family detail is trusted for an unscoped custom call.
        elif (
            not inline_voice and identity.provider == "development"
            and settings.HUGBACK_VOICE_DB_PATH.exists()
            and websocket.client and websocket.client.host in {"127.0.0.1", "::1"}
            and "demoParent" not in authentication_message
        ):
            selected = await asyncio.to_thread(get_voice_store().get, identity.user_id)
            if selected and selected["enabled"]:
                raise VoiceEnrollmentError("Custom voice is selected. Refresh voice setup before starting this call.")
        user_id = identity.user_id
        if "demoParent" in authentication_message:
            if authentication_message["demoParent"] is not True:
                raise DemoError("Invalid demo call selection.", 403)
            require_demo(
                websocket.client.host if websocket.client else None,
                websocket.headers.get("origin"), mutation=True,
            )
            demo_owner = require_demo_identity(identity)
            if inline_voice:
                raise DemoError("Demo calls require local identity and preset or portal-enrolled TTS voice.", 403)
            workflow_active = settings.HUGBACK_WORKFLOW_ENABLED
            if workflow_active and authentication_message.get("simulateWorkflowConsent") is not True:
                raise DemoError("Acknowledge synthetic Planner and Critic processing before calling.", 403)
            demo_store = get_demo_store()
            demo_state = await asyncio.to_thread(
                demo_store.start_call, demo_owner, session_id,
                authentication_message.get("demoRecipientId"),
                authentication_message.get("demoRecipientRevision"),
                authentication_message.get("voiceProfileId"),
            )
            if voice_key:
                speaking_form = speaking_form_for_call(
                    custom_voice=True, child_gender=demo_state.get("childGender"),
                )
            # The selector is untrusted. Membership/revision/voice are validated
            # against this browser owner's family before choosing memory scope.
            user_id = demo_state["parentId"]
            signal_generation = demo_state["wellbeingSharing"]["generation"]
            tone_generation = demo_state["toneContinuity"]["generation"]
            transcript_generation = demo_state["transcriptSharing"]["generation"]
            alert_generation = demo_state["alertSharing"]["generation"]
            signal_collector = SignalCollector(
                enabled=bool(demo_state["wellbeingSharing"]["enabled"]
                             or demo_state["toneContinuity"]["enabled"])
            )
    except DemoError as exc:
        await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        await websocket.close(code=1008)
        return
    except VoiceEnrollmentError as exc:
        # Safe, fixed messages only: no audio, signatures, or model output.
        await websocket.send_text(
            json.dumps({"type": "error", "code": "voice_selection_rejected", "message": str(exc)})
        )
        await websocket.close(code=1008)
        return
    except (
        AuthenticationError,
        json.JSONDecodeError,
        asyncio.TimeoutError,
    ) as exc:
        logger.warning("WebSocket authentication rejected for %s: %s", client_ip, exc)
        await websocket.send_text(
            json.dumps({"type": "error", "message": "Unable to authenticate this call"})
        )
        await websocket.close(code=1008)
        return
    except Exception:
        await websocket.send_text(json.dumps({"type": "error", "message": "Local call setup is unavailable."}))
        await websocket.close(code=1011)
        return

    try:
        model = settings.HUGBACK_MODEL
        followup_context = ""
        if demo_state or settings.FOLLOWUPS_ENABLED:
            # Do not let legacy unfiltered semantic memories reintroduce a
            # resolved, expired, or forgotten concern in the canonical pilot.
            memory_service = DisabledMemoryService("canonical follow-up mode")
            try:
                followups = get_demo_coordinator(demo_store) if demo_state else get_followup_coordinator()
                followup_plan = await asyncio.wait_for(followups.begin(user_id, session_id), timeout=3)
                followup_context = context_card(followup_plan)
            except Exception:
                followups = None
                logger.warning("Follow-up context unavailable session=%s", session_id)
                followup_context = (
                    "Cross-session memory is unavailable. Do not invent remembered "
                    "facts or promise this call will be remembered."
                )
        else:
            memory_service = get_memory_service()
        memory_context = await memory_service.initial_context(user_id)
        if workflow_active:
            conversation_plan, planner_status = await prepare_call(demo_state, followup_plan)
            await asyncio.to_thread(demo_store.workflow_checkpoint, user_id, session_id,
                                    {"planner": planner_status})
        client = create_genai_client()
        # Standard audio and replicated TTS share this conversation policy;
        # the selected voice changes only the audio delivery path below.
        live_config = create_live_config(
            memory_context=render_memory_context(memory_context),
            enable_memory_tool=memory_service.enabled,
            voice_sample_audio=inline_voice.sample if inline_voice else None,
            consent_audio=inline_voice.consent if inline_voice else None,
            followup_context=followup_context,
            enable_followup_tools=followups is not None and followup_plan is not None,
            background_context=(background_context(demo_state) + tone_context(demo_state)) if demo_state else "",
            wellbeing_signal_context=(
                (SIGNAL_CONTEXT if demo_state["wellbeingSharing"]["enabled"] else "")
                + (TONE_SIGNAL_CONTEXT if demo_state["toneContinuity"]["enabled"] else "")
            ) if demo_state else "",
            enable_wellbeing_signal_tool=signal_collector.enabled,
            conversation_plan_context=plan_context(conversation_plan, demo_state),
            speaking_form=speaking_form,
            preferred_language=demo_state.get("language", "auto") if demo_state else "auto",
        )
    except Exception as e:
        if demo_state:
            await asyncio.to_thread(demo_store.call_status, user_id, session_id, "failed", release=True)
        logger.error(f"Failed to initialize Hugback services: {e}", exc_info=True)
        await websocket.send_text(
            json.dumps({
                "type": "error",
                "message": (
                    "Hugback could not initialize this call. Check Gemini and memory configuration."
                ),
            })
        )
        await websocket.close(code=1011)
        return

    try:
        voice_name = (
            live_config.speech_config.voice_config.prebuilt_voice_config.voice_name
            if not inline_voice else None
        )
        voice_mode = "replicated-tts" if voice_key else "experimental-inline" if inline_voice else "preset"
        logger.info(
            "Connecting Live session=%s model=%s voice_mode=%s preset=%s",
            session_id, model, voice_mode, voice_name,
        )
        async with client.aio.live.connect(model=model, config=live_config) as live_session:
            if inline_voice:
                try:
                    require_live_consent_acknowledgement(
                        getattr(live_session, "setup_complete", None)
                    )
                except VoiceConsentError:
                    logger.warning("Live voice consent not acknowledged session=%s", session_id)
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "code": "voice_consent_unverified",
                        "message": "Google did not acknowledge voice consent. Call stopped; no preset fallback.",
                    }))
                    await websocket.close(code=1008)
                    return
            logger.info(f"Gemini Live session connected for {session_id}")
            if demo_state:
                activated = await asyncio.to_thread(demo_store.call_status, user_id, session_id, "active")
                if not activated:
                    raise DemoError("The demo call lease expired during connection. Please retry.")
            call_ready = True
            # The browser must not start recording until the upstream Gemini
            # session is ready. A WebSocket connection alone only confirms
            # that the local broker accepted the browser connection.
            await websocket.send_text(json.dumps({
                "type": "ready",
                "voice": "replicated" if voice_key else "experimental-inline" if inline_voice else "default",
                "voiceName": voice_name if not voice_key else None,
                "voiceStatus": (
                    "replicated_tts_unverified" if voice_key else
                    "consent_acknowledged_likeness_unverified" if inline_voice else "preset_configured"
                ),
                "model": model,
                "sessionId": session_id,
                **({"demo": {"familyId": demo_state["familyId"], "parentId": user_id,
                              "recipientId": user_id, "recipientLabel": demo_state["label"],
                              "backgroundCount": len(demo_state["background"])}} if demo_state else {}),
                "memoryStatus": (
                    followup_plan.memory_status if followup_plan else
                    "unavailable" if demo_state or settings.FOLLOWUPS_ENABLED else
                    "legacy" if memory_service.enabled else "disabled"
                ),
            }))

            received_audio = False
            sent_audio = False
            replicated_turn_text = ""
            tts_pending_text = ""
            tts_first_phrase = True
            tts_text_started_at = None
            async def checkpoint_audio():
                if followups and followup_plan:
                    try:
                        await asyncio.wait_for(followups.output(user_id, followup_plan), timeout=1)
                    except Exception:
                        logger.warning("Follow-up output checkpoint unavailable session=%s", session_id)

            playback = ReplicatedPlayback(
                client, websocket, voice_key=voice_key, model=settings.HUGBACK_TTS_MODEL,
                on_audio=checkpoint_audio, lookahead=settings.HUGBACK_TTS_LOOKAHEAD,
            ) if voice_key else None

            def cancel_replicated_speech():
                nonlocal tts_pending_text, replicated_turn_text, tts_first_phrase, tts_text_started_at
                tts_pending_text = ""
                replicated_turn_text = ""
                tts_first_phrase = True
                tts_text_started_at = None
                if playback:
                    playback.interrupt()

            def queue_replicated_speech(text, *, final=False):
                nonlocal tts_first_phrase
                if playback:
                    playback.enqueue(text, final=final)
                    if text:
                        if tts_first_phrase and tts_text_started_at is not None:
                            logger.info("Replicated TTS first_phrase_buffer_ms=%d",
                                        round((time.monotonic() - tts_text_started_at) * 1000))
                        tts_first_phrase = False

            async def upstream_task() -> None:
                """Reads microphone PCM audio and controls from browser and sends to Gemini."""
                nonlocal received_audio
                try:
                    while True:
                        message = await websocket.receive()

                        # Binary frame: Raw 16-bit PCM @ 16kHz
                        if "bytes" in message:
                            audio_bytes = message["bytes"]
                            if audio_bytes:
                                if not received_audio:
                                    samples = memoryview(audio_bytes).cast("h")
                                    rms = int(
                                        (sum(sample * sample for sample in samples) / len(samples))
                                        ** 0.5
                                    )
                                    peak = max(abs(sample) for sample in samples)
                                    logger.info(
                                        "Receiving microphone audio for %s "
                                        "(first chunk: %d bytes, rms=%d, peak=%d)",
                                        session_id,
                                        len(audio_bytes),
                                        rms,
                                        peak,
                                    )
                                    received_audio = True
                                await live_session.send_realtime_input(
                                    audio=types.Blob(
                                        mime_type="audio/pcm;rate=16000",
                                        data=audio_bytes,
                                    )
                                )

                        # Text frame: JSON control messages
                        elif "text" in message:
                            try:
                                data = json.loads(message["text"])
                                msg_type = data.get("type")

                                if msg_type == "text" and "text" in data:
                                    collector.add_user(str(data["text"]))
                                    await live_session.send_client_content(
                                        turns=types.Content(
                                            role="user",
                                            parts=[types.Part.from_text(text=data["text"])],
                                        ),
                                        turn_complete=True,
                                    )

                                elif msg_type == "turn_complete":
                                    logger.info(f"Client edge VAD signaled turn_complete for {session_id}")
                                    cancel_replicated_speech()
                                    await live_session.send_client_content(
                                        turn_complete=True,
                                    )

                                elif msg_type == "audio_stream_end":
                                    logger.info(
                                        "Client signaled end of speech for %s",
                                        session_id,
                                    )
                                    await live_session.send_realtime_input(
                                        audio_stream_end=True,
                                    )

                                elif msg_type == "ping":
                                    await websocket.send_text(json.dumps({"type": "pong"}))

                            except json.JSONDecodeError:
                                pass

                except (WebSocketDisconnect, RuntimeError):
                    logger.info(f"Browser disconnected for session {session_id}")
                except asyncio.CancelledError:
                    pass
                except Exception as err:
                    logger.error(f"Error in upstream_task: {err}", exc_info=True)

            async def downstream_task() -> None:
                """Receives audio and events from Gemini and streams them back to the browser."""
                nonlocal sent_audio, replicated_turn_text, tts_pending_text, tts_first_phrase, tts_text_started_at
                try:
                    # The SDK's receive() iterator represents one complete
                    # model turn and intentionally stops at turn_complete.
                    # Re-enter it for every turn so the Live session and the
                    # browser WebSocket remain open for a conversation.
                    while True:
                        async for response in live_session.receive():
                            # A provider event can contain BOTH a user transcript
                            # and a tool call. Validate privacy-tool evidence
                            # against the current utterance, not the prior turn.
                            incoming_content = response.server_content
                            if (
                                incoming_content is not None
                                and incoming_content.input_transcription
                                and incoming_content.input_transcription.text
                            ):
                                user_text = incoming_content.input_transcription.text
                                collector.add_user(user_text)
                                await websocket.send_text(
                                    json.dumps({"inputTranscription": {"text": user_text}})
                                )
                            if response.tool_call:
                                function_responses = []
                                for call in response.tool_call.function_calls:
                                    if call.name == "propose_call_wellbeing_signal":
                                        result = signal_collector.propose(call.args)
                                    elif call.name in ("claim_followup", "control_followup"):
                                        result = {"allowed": False, "changed": False}
                                        if followups and followup_plan:
                                            try:
                                                args = call.args if isinstance(call.args, dict) else {}
                                                if call.name == "claim_followup":
                                                    result = await asyncio.wait_for(
                                                        followups.claim(
                                                            user_id, followup_plan,
                                                            latest_user_text=collector.latest_user_text(),
                                                        ), timeout=3,
                                                    )
                                                else:
                                                    result = await asyncio.wait_for(
                                                        followups.control(
                                                            user_id, followup_plan,
                                                            args.get("action"), args.get("topic"),
                                                            args.get("evidence", ""),
                                                            collector.latest_user_text(),
                                                        ), timeout=3,
                                                    )
                                                    if demo_state and args.get("action") == "revoke_all" and result.get("changed"):
                                                        await asyncio.to_thread(demo_store.forget_background, user_id)
                                            except Exception:
                                                logger.warning("Follow-up tool unavailable session=%s", session_id)
                                                result = {
                                                    "allowed": False, "changed": False,
                                                    "reason": "Memory operation unavailable; do not claim success.",
                                                }
                                    elif call.name != "recall_memory":
                                        result = {"error": "Unknown memory tool"}
                                    else:
                                        args = call.args or {}
                                        topic = str(args.get("topic", ""))
                                        try:
                                            facts = await memory_service.search(
                                                user_id,
                                                topic,
                                                settings.MEMORY_SEARCH_LIMIT,
                                            )
                                            result = {
                                                "memories": facts,
                                                "guidance": (
                                                    "Treat these as possibly outdated facts. "
                                                    "Use them naturally and verify when needed."
                                                ),
                                            }
                                        except Exception as exc:
                                            logger.warning(
                                                "Live memory lookup failed for %s: %s",
                                                session_id,
                                                exc,
                                            )
                                            result = {"memories": []}
                                    if workflow_active and call.name in ("claim_followup", "control_followup") and len(tool_outcomes) < 65:
                                        tool_outcomes.append(ToolOutcome(
                                            name=call.name, succeeded=bool(result.get("allowed") or result.get("changed")),
                                        ))
                                    function_responses.append(
                                        types.FunctionResponse(
                                            id=call.id,
                                            name=call.name,
                                            response=result,
                                            scheduling=types.FunctionResponseScheduling.WHEN_IDLE,
                                        )
                                    )
                                await live_session.send_tool_response(
                                    function_responses=function_responses
                                )

                            server_content = response.server_content
                            if server_content is not None:
                                # Interruption takes precedence over stale bundled output (Gemini detected user speech)
                                if server_content.interrupted:
                                    logger.info(f"Gemini signaled interrupted for {session_id}")
                                    cancel_replicated_speech()
                                    replicated_turn_text = ""
                                    await websocket.send_text(json.dumps({"interrupted": True}))
                                    if followups and followup_plan:
                                        try:
                                            await asyncio.wait_for(
                                                followups.output(user_id, followup_plan, interrupted=True), timeout=1,
                                            )
                                        except Exception:
                                            logger.warning("Follow-up interruption checkpoint unavailable session=%s", session_id)
                                    continue

                                # 1. Audio and text parts from model turn
                                if server_content.model_turn is not None:
                                    for part in server_content.model_turn.parts:
                                        if part.inline_data and part.inline_data.data:
                                            # Gemini Live currently rejects replicated voice
                                            # IDs. For enrolled users, discard its prebuilt
                                            # audio and synthesize the transcription through
                                            # the supported Flash-Lite TTS endpoint instead.
                                            if voice_key:
                                                continue
                                            if not sent_audio:
                                                logger.info(
                                                    "Streaming Gemini audio response for %s",
                                                    session_id,
                                                )
                                                sent_audio = True
                                            # Base64 encode binary audio chunk for browser client
                                            audio_b64 = base64.b64encode(part.inline_data.data).decode("utf-8")
                                            payload = {
                                                "content": {
                                                    "parts": [{
                                                        "inlineData": {
                                                            "mimeType": part.inline_data.mime_type or "audio/pcm;rate=24000",
                                                            "data": audio_b64,
                                                        }
                                                    }]
                                                }
                                            }
                                            await websocket.send_text(json.dumps(payload))
                                            if followups and followup_plan:
                                                try:
                                                    await asyncio.wait_for(
                                                        followups.output(user_id, followup_plan), timeout=1,
                                                    )
                                                except Exception:
                                                    logger.warning("Follow-up output checkpoint unavailable session=%s", session_id)

                                        if part.text and not voice_key:
                                            await websocket.send_text(
                                                json.dumps({"outputTranscription": {"text": part.text}})
                                            )

                                # 2. Output speech transcription from server
                                if (
                                    server_content.output_transcription
                                    and server_content.output_transcription.text
                                ):
                                    previous_text = replicated_turn_text
                                    replicated_turn_text = merge_transcription(
                                        replicated_turn_text,
                                        server_content.output_transcription.text,
                                    )
                                    if voice_key and replicated_turn_text.startswith(previous_text):
                                        if tts_text_started_at is None:
                                            tts_text_started_at = time.monotonic()
                                        tts_pending_text += replicated_turn_text[len(previous_text):]
                                        ready, tts_pending_text = split_ready_speech(
                                            tts_pending_text,
                                            first_phrase_chars=settings.HUGBACK_TTS_FIRST_PHRASE_CHARS if tts_first_phrase else None,
                                        )
                                        for segment in ready:
                                            queue_replicated_speech(segment)
                                    collector.add_model(
                                        server_content.output_transcription.text
                                    )
                                    if not voice_key:
                                        await websocket.send_text(
                                            json.dumps({
                                                "outputTranscription": {
                                                    "text": server_content.output_transcription.text
                                                }
                                            })
                                        )

                                # 4. Turn completion signal
                                if server_content.turn_complete:
                                    collector.complete_turn()
                                    if voice_key:
                                        ready, tts_pending_text = split_ready_speech(
                                            tts_pending_text,
                                            final=True,
                                            first_phrase_chars=settings.HUGBACK_TTS_FIRST_PHRASE_CHARS if tts_first_phrase else None,
                                        )
                                        if ready:
                                            for segment in ready[:-1]:
                                                queue_replicated_speech(segment)
                                            queue_replicated_speech(
                                                ready[-1], final=True
                                            )
                                        else:
                                            # A zero-text marker closes a turn whose
                                            # complete sentences are already queued.
                                            queue_replicated_speech("", final=True)
                                        replicated_turn_text = ""
                                        tts_first_phrase = True
                                        tts_text_started_at = None
                                    else:
                                        replicated_turn_text = ""
                                        await websocket.send_text(json.dumps({"turnComplete": True}))


                except asyncio.CancelledError:
                    pass
                except Exception as err:
                    logger.warning("Downstream speech stream stopped")
                    try:
                        await websocket.send_text(
                            json.dumps({
                                "type": "error",
                                "message": "Speech stream stopped. Please retry the call; no voice fallback was used.",
                            })
                        )
                    except Exception:
                        pass

            # Run both upstream and downstream tasks concurrently
            upstream = asyncio.create_task(upstream_task(), name=f"upstream-{session_id}")
            downstream = asyncio.create_task(downstream_task(), name=f"downstream-{session_id}")

            try:
                done, pending = await asyncio.wait(
                    [upstream, downstream] + ([playback.task] if playback else []),
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=max(0, min(600, (
                        datetime.fromisoformat(demo_state["activeCall"]["leaseUntil"])
                        - datetime.now(timezone.utc)
                    ).total_seconds() - 30)) if demo_state else None,
                )
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                if playback:
                    await playback.close()
                if not done:
                    await websocket.send_text(json.dumps({
                        "type": "error", "message": "The ten-minute local demo call limit was reached.",
                    }))
                    await websocket.close(code=1000)
            except Exception as e:
                logger.error(f"Error managing tasks for {session_id}: {e}", exc_info=True)
            finally:
                upstream.cancel()
                downstream.cancel()
                await asyncio.gather(upstream, downstream, return_exceptions=True)
                if playback:
                    await playback.close()

    except Exception as e:
        provider_code, detail = live_failure_detail(e, connected=call_ready)
        logger.error("Gemini Live %s failed (%s, provider_code=%s)",
                     "stream" if call_ready else "setup", type(e).__name__, provider_code)
        try:
            await websocket.send_text(
                json.dumps({
                    "type": "error",
                    "code": "live_stream_failed" if call_ready else "live_setup_failed",
                    "message": detail,
                })
            )
        except Exception:
            pass
    finally:
        try:
            close_async = getattr(client.aio, "aclose", None)
            if close_async:
                await asyncio.wait_for(close_async(), timeout=3)
            close_sync = getattr(client, "close", None)
            if close_sync:
                close_sync()
        except Exception:
            logger.warning("Provider client cleanup did not complete")
        ended_at = datetime.now(timezone.utc)
        turns = collector.finalize()
        if user_id:
            try:
                if demo_state:
                    async def finish_demo():
                        outcome = "failed" if not call_ready else "completed"
                        memory_error = None
                        alert_pending = False
                        transcript_saved = False
                        async def memory_checkpoint(stage):
                            # Observability is best-effort, not the memory commit.
                            if not workflow_active:
                                return
                            try:
                                await asyncio.to_thread(demo_store.workflow_checkpoint, user_id, session_id,
                                                        {"reconciler": stage})
                            except Exception:
                                logger.warning("Memory workflow status unavailable session=%s", session_id)
                        try:
                            await asyncio.to_thread(demo_store.call_status, user_id, session_id, "processing")
                            if contains_privacy_request(turns):
                                # Imported context is distinct from optional
                                # wellbeing memory; honor privacy even if that
                                # optional extractor is disabled/unavailable.
                                await asyncio.to_thread(demo_store.forget_background, user_id)
                            if contains_signal_privacy_request(turns):
                                try:
                                    await asyncio.to_thread(
                                        demo_store.revoke_wellbeing_sharing,
                                        user_id, signal_generation,
                                    )
                                except Exception:
                                    logger.warning("Local demo signal revocation was not saved session=%s", session_id)
                            if (contains_privacy_request(turns) or contains_signal_privacy_request(turns)
                                    or contains_tone_privacy_request(turns)):
                                try:
                                    await asyncio.to_thread(
                                        demo_store.revoke_tone_continuity,
                                        user_id, tone_generation,
                                    )
                                except Exception:
                                    logger.warning("Local demo tone-continuity revocation was not saved session=%s", session_id)
                            if contains_privacy_request(turns) or contains_signal_privacy_request(turns):
                                try:
                                    await asyncio.to_thread(
                                        demo_store.revoke_transcript_sharing, user_id, transcript_generation,
                                    )
                                except Exception:
                                    logger.warning("Local demo transcript revocation was not saved session=%s", session_id)
                            if (contains_privacy_request(turns) or contains_signal_privacy_request(turns)
                                    or asks_not_to_alert(turns)):
                                try:
                                    await asyncio.to_thread(
                                        demo_store.revoke_alert_sharing, user_id, alert_generation,
                                    )
                                except Exception:
                                    logger.warning("Local demo alert revocation was not saved session=%s", session_id)
                            if followups and followup_plan:
                                try:
                                    result = await asyncio.wait_for(
                                        followups.finish(user_id, followup_plan, turns), timeout=25,
                                    )
                                    await memory_checkpoint(result)
                                    if result in ("privacy_hold", "revoked"):
                                        outcome = result
                                        # Safe over-removal after unhandled privacy intent.
                                        await asyncio.to_thread(demo_store.forget_background, user_id)
                                except Exception as exc:
                                    outcome = "memory_failed"
                                    memory_error = memory_error_code(exc)
                                    await memory_checkpoint("failed")
                                    logger.warning("Demo memory update failed session=%s code=%s", session_id, memory_error)
                            elif (any(turn.role == "user" for turn in turns)
                                  and demo_state["memory"]["consent"]
                                  and not demo_state["memory"].get("privacy_hold")):
                                outcome = "memory_failed"
                                memory_error = "context_unavailable"
                                await memory_checkpoint("failed")
                            else:
                                await memory_checkpoint("skipped")
                            signal = signal_collector.publishable(turns)
                            if signal is not None and demo_state["wellbeingSharing"]["enabled"]:
                                try:
                                    await asyncio.to_thread(
                                        demo_store.record_wellbeing_signal,
                                        user_id, session_id, signal_generation, signal,
                                        model=settings.HUGBACK_MODEL,
                                    )
                                except Exception:
                                    # Signals are optional: never relabel a successful
                                    # call or memory update because this path failed.
                                    logger.warning("Local demo wellbeing signal was not saved session=%s", session_id)
                            tone_signal = signal_collector.tone_publishable(turns)
                            if (tone_signal is not None and demo_state["toneContinuity"]["enabled"]
                                    and not contains_tone_privacy_request(turns)):
                                try:
                                    await asyncio.to_thread(
                                        demo_store.record_tone_observation,
                                        user_id, session_id, tone_generation, tone_signal,
                                    )
                                except Exception:
                                    logger.warning("Local demo tone note was not saved session=%s", session_id)
                            if demo_state["transcriptSharing"]["enabled"]:
                                try:
                                    transcript_saved = await asyncio.to_thread(
                                    demo_store.record_transcript, user_id, session_id,
                                    transcript_generation, summary_input(turns),
                                    )
                                except Exception as exc:
                                    logger.warning("Local demo summary input failed session=%s code=%s",
                                                   session_id, type(exc).__name__)
                            if call_ready and transcript_saved and demo_state["alertSharing"]["enabled"]:
                                topic = detect_topic(turns)
                                if topic and not (contains_privacy_request(turns)
                                                  or contains_signal_privacy_request(turns)
                                                  or asks_not_to_alert(turns)):
                                    try:
                                        alert_pending = await asyncio.to_thread(
                                            demo_store.reserve_alert, user_id, session_id,
                                            alert_generation, topic,
                                            email_configured=alert_email_configured(),
                                        )
                                    except Exception:
                                        logger.warning("Local demo call notice was not recorded session=%s", session_id)
                        except asyncio.CancelledError:
                            outcome = "memory_failed"
                            memory_error = "processing_interrupted"
                            raise
                        except Exception:
                            outcome = "memory_failed"
                            memory_error = "storage_unavailable"
                            logger.warning("Demo memory finalization failed session=%s code=%s", session_id, memory_error)
                        finally:
                            try:
                                await asyncio.to_thread(
                                    demo_store.call_status, user_id, session_id, outcome, release=True,
                                    quality_pending=workflow_active and call_ready,
                                    memory_error=memory_error,
                                )
                            except Exception:
                                logger.warning("Local demo finalization unavailable session=%s", session_id)
                        if workflow_active and call_ready:
                            # Release the call lease first. Critic cannot delay next-call memory.
                            critic_task = asyncio.create_task(finish_quality_review(
                                demo_store, user_id, session_id, demo_state, turns, tool_outcomes, outcome,
                            ))
                            _demo_finalizers.add(critic_task)
                            critic_task.add_done_callback(_demo_finalizers.discard)
                        if call_ready and transcript_saved and not (
                            contains_privacy_request(turns) or contains_signal_privacy_request(turns)
                        ):
                            async def save_summary():
                                eligible = await asyncio.to_thread(
                                    demo_store.summary_eligible, user_id, session_id, transcript_generation,
                                )
                                if not eligible:
                                    return
                                summary = await summarize_call(turns)
                                try:
                                    await asyncio.to_thread(
                                        demo_store.record_call_summary, user_id, session_id,
                                        transcript_generation, summary,
                                    )
                                except Exception:
                                    logger.warning("Synthetic call summary was not saved session=%s", session_id)
                            summary_task = asyncio.create_task(save_summary())
                            _demo_finalizers.add(summary_task)
                            summary_task.add_done_callback(_demo_finalizers.discard)
                        if alert_pending:
                            async def deliver_alert():
                                details = await asyncio.to_thread(
                                    demo_store.claim_alert_send, user_id, session_id, alert_generation,
                                )
                                if not details:
                                    return
                                delivered = False
                                try:
                                    await asyncio.to_thread(
                                        send_test_notice, details["label"], details["startedAt"], details["email"],
                                        details.get("childName"),
                                    )
                                    delivered = True
                                except Exception as exc:
                                    logger.warning("Synthetic email notice failed session=%s code=%s",
                                                   session_id, type(exc).__name__)
                                try:
                                    await asyncio.to_thread(
                                        demo_store.finish_alert_send, user_id, session_id,
                                        alert_generation, delivered=delivered,
                                    )
                                except Exception:
                                    logger.warning("Synthetic email status was not saved session=%s", session_id)
                            alert_task = asyncio.create_task(deliver_alert())
                            _demo_finalizers.add(alert_task)
                            alert_task.add_done_callback(_demo_finalizers.discard)
                    finalizer = asyncio.create_task(finish_demo())
                    _demo_finalizers.add(finalizer)
                    finalizer.add_done_callback(_demo_finalizers.discard)
                    await asyncio.shield(finalizer)
                elif settings.FOLLOWUPS_ENABLED:
                    # Canonical pilot retains NO raw transcript. Extraction is
                    # awaited and bounded; only source-backed concern evidence
                    # is committed. Durable retry/outbox is a separate gate.
                    if followups and followup_plan:
                        try:
                            await asyncio.wait_for(
                                followups.finish(user_id, followup_plan, turns),
                                timeout=25,
                            )
                        except Exception:
                            logger.warning("Follow-up consolidation failed session=%s", session_id)
                    logger.info("Canonical memory session ended session=%s", session_id)
                else:
                    store = get_session_store()
                    if store.enabled:
                        await store.save_session(
                            user_id=user_id,
                            session_id=session_id,
                            started_at=started_at,
                            ended_at=ended_at,
                            turns=turns,
                        )
                        if any(turn.role == "user" for turn in turns):
                            await dispatch_memory_processing(
                                ProcessMemoryRequest(
                                    user_id=user_id,
                                    session_id=session_id,
                                )
                            )
                    elif settings.MEMORY_ENABLED:
                        logger.error(
                            "Memory is enabled but Firestore is disabled; session %s "
                            "cannot be processed durably",
                            session_id,
                        )
            except Exception as exc:
                logger.error(
                    "Failed to persist/process session %s: %s",
                    session_id,
                    exc,
                    exc_info=True,
                )
        logger.info(f"Cleaned up session {session_id}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT)
