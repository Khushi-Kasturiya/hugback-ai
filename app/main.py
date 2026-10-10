"""FastAPI application for Elara Multimodal Live Audio WebSocket broker.

Uses official Google GenAI SDK (google-genai) with direct support for both
Google AI Studio GEMINI_API_KEY and Vertex AI Application Default Credentials.
"""

import asyncio
import base64
import json
import logging
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from google.genai import types

from app.agent.live_session import create_genai_client, create_live_config
from app.config import settings

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
    return {
        "status": "healthy",
        "auth_mode": auth_mode,
        "has_api_key": bool(settings.GEMINI_API_KEY),
        "project": settings.GOOGLE_CLOUD_PROJECT,
        "location": settings.GOOGLE_CLOUD_LOCATION,
        "model": settings.ELARA_MODEL,
        "voice": settings.ELARA_VOICE_NAME,
    }


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
    session_id = websocket.query_params.get("session_id", f"session-{uuid.uuid4().hex[:6]}")

    logger.info(f"Incoming WebSocket connection from {client_ip} [session: {session_id}]")
    await websocket.accept()

    try:
        client = create_genai_client()
        live_config = create_live_config()
    except Exception as e:
        logger.error(f"Failed to initialize Google GenAI Client: {e}", exc_info=True)
        await websocket.send_text(
            json.dumps({
                "type": "error",
                "message": (
                    f"Authentication error: {str(e)}. "
                    "Please set GEMINI_API_KEY in .env or run 'gcloud auth application-default login'."
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
            await websocket.send_text(json.dumps({"type": "ready"}))

            received_audio = False
            sent_audio = False

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
                                    await live_session.send_client_content(
                                        turns=types.Content(
                                            role="user",
                                            parts=[types.Part.from_text(text=data["text"])],
                                        ),
                                        turn_complete=True,
                                    )

                                elif msg_type == "turn_complete":
                                    logger.info(f"Client edge VAD signaled turn_complete for {session_id}")
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
                nonlocal sent_audio
                try:
                    # The SDK's receive() iterator represents one complete
                    # model turn and intentionally stops at turn_complete.
                    # Re-enter it for every turn so the Live session and the
                    # browser WebSocket remain open for a conversation.
                    while True:
                        async for response in live_session.receive():
                            server_content = response.server_content
                            if server_content is not None:
                                # 1. Audio and text parts from model turn
                                if server_content.model_turn is not None:
                                    for part in server_content.model_turn.parts:
                                        if part.inline_data and part.inline_data.data:
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
                                    await websocket.send_text(
                                        json.dumps({
                                            "inputTranscription": {
                                                "text": server_content.input_transcription.text
                                            }
                                        })
                                    )

                                # 4. Turn completion signal
                                if server_content.turn_complete:
                                    await websocket.send_text(json.dumps({"turnComplete": True}))

                                # 5. Interruption signal (Gemini detected user speech)
                                if server_content.interrupted:
                                    logger.info(f"Gemini signaled interrupted for {session_id}")
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
        logger.info(f"Cleaned up session {session_id}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT)
