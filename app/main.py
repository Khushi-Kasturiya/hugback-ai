"""FastAPI application for Elara's authenticated live-audio WebSocket broker.

Uses official Google GenAI SDK (google-genai) with direct support for both
Google AI Studio GEMINI_API_KEY and Vertex AI Application Default Credentials.
"""

import asyncio
import base64
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from google.genai import types
from pydantic import BaseModel

from app.agent.live_session import create_genai_client, create_live_config
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
from app.memory.service import get_memory_service, render_memory_context
from app.memory.store import get_session_store
from app.memory.transcript import TranscriptCollector, merge_transcription
from app.voice.service import (
    VoiceEnrollmentError,
    create_replicated_voice_key,
    parse_inline_voice,
    parse_voice_key,
    split_ready_speech,
    stream_replicated_speech,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("elara.broker")

# Initialize FastAPI
app = FastAPI(
    title="Elara Multimodal Live Audio Broker",
    version="0.1.0",
    description="Bidirectional low-latency audio broker connecting to Gemini Multimodal Live API",
)

# CORS Middleware for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz():
    """Health check endpoint."""
    auth_mode = "api_key" if settings.GEMINI_API_KEY else "vertex_ai"
    memory_service = get_memory_service()
    session_store = get_session_store()
    return {
        "status": "healthy",
        "auth_mode": auth_mode,
        "has_api_key": bool(settings.GEMINI_API_KEY),
        "project": settings.GOOGLE_CLOUD_PROJECT,
        "location": settings.GOOGLE_CLOUD_LOCATION,
        "model": settings.ELARA_MODEL,
        "voice": settings.ELARA_VOICE_NAME,
        "caller_auth": settings.ELARA_AUTH_MODE,
        "memory_configured": settings.MEMORY_ENABLED,
        "memory_operational": memory_service.enabled,
        "memory_error": getattr(memory_service, "reason", None),
        "firestore_configured": settings.FIRESTORE_ENABLED,
        "firestore_operational": session_store.enabled,
        "firestore_error": getattr(session_store, "reason", None),
        "memory_processing": settings.MEMORY_PROCESSING_MODE,
    }


@app.post("/internal/memory/process")
async def memory_process_endpoint(payload: ProcessMemoryRequest, request: Request):
    """Cloud Tasks target for retryable, post-call memory consolidation."""
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
    try:
        identity = await authenticate_http_headers(request.headers)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    context = await get_memory_service().inspect(identity.user_id)
    return {"profiles": context.profiles, "facts": context.facts}


@app.delete("/api/memories")
async def delete_memories(request: Request):
    """Delete Memory Bank facts/profiles and persisted transcripts for one user."""
    try:
        identity = await authenticate_http_headers(request.headers)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    await get_memory_service().delete_all(identity.user_id)
    await get_session_store().delete_user_data(identity.user_id)
    return {"status": "deleted"}


class VoiceEnrollmentRequest(BaseModel):
    voiceSampleAudio: str
    consentAudio: str


@app.post("/api/voice/enroll")
async def enroll_voice(payload: VoiceEnrollmentRequest, request: Request):
    """Create Google's seven-day stateless voice key after verifying consent."""
    try:
        await authenticate_http_headers(request.headers)
        recordings = parse_inline_voice(payload.model_dump())
        if recordings is None:
            raise VoiceEnrollmentError("Both voice recordings are required")
    except (AuthenticationError, VoiceEnrollmentError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    client = create_genai_client()

    try:
        voice_key = await asyncio.to_thread(
            create_replicated_voice_key,
            client,
            recordings,
        )
    except Exception as exc:
        message = str(exc)
        if "Paid Quota Tier 1" in message or "PERMISSION_DENIED" in message:
            raise HTTPException(
                status_code=402,
                detail=(
                    "Google Voice Replication requires Gemini API Paid Tier 1 "
                    "with an active API billing balance. Confirm this API key belongs "
                    "to the upgraded project, then try again."
                ),
            ) from exc
        logger.error("Voice replication provisioning failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=502,
            detail="Google could not create the replicated voice. Check the recordings and try again.",
        ) from exc

    return {"voiceKey": voice_key, "expiresInSeconds": 7 * 24 * 60 * 60}


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

    logger.info(f"Incoming WebSocket connection from {client_ip} [session: {session_id}]")
    await websocket.accept()

    try:
        authentication_text = await asyncio.wait_for(websocket.receive_text(), timeout=15)
        authentication_message = json.loads(authentication_text)
        identity = await authenticate_message(authentication_message)
        voice_key = parse_voice_key(authentication_message)
        user_id = identity.user_id
    except (
        AuthenticationError,
        VoiceEnrollmentError,
        json.JSONDecodeError,
        asyncio.TimeoutError,
    ) as exc:
        logger.warning("WebSocket authentication rejected for %s: %s", client_ip, exc)
        await websocket.send_text(
            json.dumps({"type": "error", "message": "Unable to authenticate this call"})
        )
        await websocket.close(code=1008)
        return

    try:
        memory_service = get_memory_service()
        memory_context = await memory_service.initial_context(user_id)
        client = create_genai_client()
        live_config = create_live_config(
            memory_context=render_memory_context(memory_context),
            enable_memory_tool=memory_service.enabled,
        )
    except Exception as e:
        logger.error(f"Failed to initialize Elara services: {e}", exc_info=True)
        await websocket.send_text(
            json.dumps({
                "type": "error",
                "message": (
                    "Elara could not initialize this call. Check Gemini and memory configuration."
                ),
            })
        )
        await websocket.close(code=1011)
        return

    try:
        logger.info(f"Connecting to Gemini Live API with model={settings.ELARA_MODEL}...")
        async with client.aio.live.connect(model=settings.ELARA_MODEL, config=live_config) as live_session:
            logger.info(f"Gemini Live session connected for {session_id}")
            # The browser must not start recording until the upstream Gemini
            # session is ready. A WebSocket connection alone only confirms
            # that the local broker accepted the browser connection.
            await websocket.send_text(json.dumps({
                "type": "ready",
                "voice": "replicated" if voice_key else "default",
            }))

            received_audio = False
            sent_audio = False
            replicated_turn_text = ""
            tts_pending_text = ""
            tts_generation = 0
            tts_queue: asyncio.Queue[tuple[str, bool]] = asyncio.Queue()
            tts_worker_task: asyncio.Task[None] | None = None

            def cancel_replicated_speech() -> None:
                nonlocal tts_generation, tts_queue, tts_worker_task, tts_pending_text
                tts_generation += 1
                tts_pending_text = ""
                if tts_worker_task is not None and not tts_worker_task.done():
                    tts_worker_task.cancel()
                tts_queue = asyncio.Queue()
                tts_worker_task = None

            async def replicated_speech_worker(
                queue: asyncio.Queue[tuple[str, bool]], generation: int
            ) -> None:
                """Synthesize queued phrases in order and stream each immediately."""
                nonlocal sent_audio
                try:
                    while True:
                        text, final = await queue.get()
                        if text:
                            synthesis_started = asyncio.get_running_loop().time()
                            chunk_count = 0
                            async for audio in stream_replicated_speech(
                                client,
                                voice_key=voice_key or "",
                                text=text,
                                model=settings.ELARA_TTS_MODEL,
                            ):
                                if generation != tts_generation:
                                    return
                                chunk_count += 1
                                if chunk_count == 1:
                                    logger.info(
                                        "Replicated TTS first audio for %s in %.2fs "
                                        "(%d chars)",
                                        session_id,
                                        asyncio.get_running_loop().time()
                                        - synthesis_started,
                                        len(text),
                                    )
                                sent_audio = True
                                await websocket.send_text(json.dumps({
                                    "content": {
                                        "parts": [{
                                            "inlineData": {
                                                "mimeType": (
                                                    f"audio/pcm;rate={audio.sample_rate}"
                                                ),
                                                "data": base64.b64encode(
                                                    audio.pcm
                                                ).decode("ascii"),
                                            }
                                        }]
                                    }
                                }))
                            logger.info(
                                "Replicated TTS segment completed for %s in %.2fs "
                                "(%d chunks)",
                                session_id,
                                asyncio.get_running_loop().time() - synthesis_started,
                                chunk_count,
                            )
                        if final:
                            if generation == tts_generation:
                                await websocket.send_text(
                                    json.dumps({"turnComplete": True})
                                )
                            return
                except asyncio.CancelledError:
                    return
                except Exception as exc:
                    logger.error(
                        "Replicated voice synthesis failed for %s: %s",
                        session_id,
                        exc,
                        exc_info=True,
                    )
                    try:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "Google could not synthesize the replicated voice.",
                        }))
                    except Exception:
                        pass

            def queue_replicated_speech(text: str, *, final: bool = False) -> None:
                nonlocal tts_worker_task
                if tts_worker_task is None or tts_worker_task.done():
                    generation = tts_generation
                    queue = tts_queue
                    tts_worker_task = asyncio.create_task(
                        replicated_speech_worker(queue, generation),
                        name=f"tts-{session_id}",
                    )
                tts_queue.put_nowait((text, final))

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
                nonlocal sent_audio, replicated_turn_text, tts_pending_text
                try:
                    # The SDK's receive() iterator represents one complete
                    # model turn and intentionally stops at turn_complete.
                    # Re-enter it for every turn so the Live session and the
                    # browser WebSocket remain open for a conversation.
                    while True:
                        async for response in live_session.receive():
                            if response.tool_call:
                                function_responses = []
                                for call in response.tool_call.function_calls:
                                    if call.name != "recall_memory":
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

                                        if part.text:
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
                                        tts_pending_text += replicated_turn_text[len(previous_text):]
                                        ready, tts_pending_text = split_ready_speech(
                                            tts_pending_text
                                        )
                                        for segment in ready:
                                            queue_replicated_speech(segment)
                                    collector.add_model(
                                        server_content.output_transcription.text
                                    )
                                    await websocket.send_text(
                                        json.dumps({
                                            "outputTranscription": {
                                                "text": server_content.output_transcription.text
                                            }
                                        })
                                    )

                                # 3. Input user speech transcription from server
                                if (
                                    server_content.input_transcription
                                    and server_content.input_transcription.text
                                ):
                                    collector.add_user(
                                        server_content.input_transcription.text
                                    )
                                    await websocket.send_text(
                                        json.dumps({
                                            "inputTranscription": {
                                                "text": server_content.input_transcription.text
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
                                    else:
                                        replicated_turn_text = ""
                                        await websocket.send_text(json.dumps({"turnComplete": True}))

                                # 5. Interruption signal (Gemini detected user speech)
                                if server_content.interrupted:
                                    logger.info(f"Gemini signaled interrupted for {session_id}")
                                    cancel_replicated_speech()
                                    replicated_turn_text = ""
                                    await websocket.send_text(json.dumps({"interrupted": True}))

                except asyncio.CancelledError:
                    pass
                except Exception as err:
                    logger.warning(f"Error in downstream_task: {err}")
                    try:
                        await websocket.send_text(
                            json.dumps({
                                "type": "error",
                                "message": f"Gemini stream error: {str(err)}",
                            })
                        )
                    except Exception:
                        pass

            # Run both upstream and downstream tasks concurrently
            upstream = asyncio.create_task(upstream_task(), name=f"upstream-{session_id}")
            downstream = asyncio.create_task(downstream_task(), name=f"downstream-{session_id}")

            try:
                done, pending = await asyncio.wait(
                    [upstream, downstream],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                cancel_replicated_speech()
                if tts_worker_task is not None:
                    try:
                        await tts_worker_task
                    except asyncio.CancelledError:
                        pass
            except Exception as e:
                logger.error(f"Error managing tasks for {session_id}: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Gemini live connection failed: {e}", exc_info=True)
        try:
            await websocket.send_text(
                json.dumps({
                    "type": "error",
                    "message": f"Connection failed: {str(e)}",
                })
            )
        except Exception:
            pass
    finally:
        ended_at = datetime.now(timezone.utc)
        turns = collector.finalize()
        if user_id:
            try:
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
