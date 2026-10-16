"""Import, health, and WebSocket regression tests with no Google requests."""

import asyncio
import base64
import io
import unittest
import wave
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from google.genai import types

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

# Import the actual app, not just helpers: missing request-path modules must fail
# the test suite before a broken commit can reach a local Uvicorn startup.
from app.main import app
from app.memory.service import DisabledMemoryService
from app.memory.store import DisabledSessionStore


def synthetic_voice_message():
    """Silence generated in memory; no real speaker or private file."""
    def encoded_wav(seconds):
        output = io.BytesIO()
        with wave.open(output, "wb") as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(24_000)
            target.writeframes(b"\0\0" * (seconds * 24_000))
        return base64.b64encode(output.getvalue()).decode("ascii")

    return {
        "type": "authenticate",
        "userId": "local-test-user",
        "voiceSampleAudio": encoded_wav(10),
        "consentAudio": encoded_wav(2),
    }


class StartupTests(unittest.TestCase):
    def setUp(self):
        for replacement in (
            patch("app.main.get_memory_service", return_value=DisabledMemoryService()),
            patch("app.main.get_session_store", return_value=DisabledSessionStore()),
            patch("app.main.settings.MEMORY_ENABLED", False),
            patch("app.main.settings.FIRESTORE_ENABLED", False),
            patch("app.main.settings.FOLLOWUPS_ENABLED", False),
            patch("app.main.settings.HUGBACK_AUTH_MODE", "development"),
            patch("app.main.settings.HUGBACK_LIVE_VOICE_MODE", "preset"),
            patch("app.main.settings.HUGBACK_VOICE_NAME", "Aoede"),
            # Private test-file settings must never turn into a global voice for
            # ordinary callers or be read by /health and preset sessions.
            patch("app.main.settings.HUGBACK_VOICE_REFERENCE_PATH", "/nonexistent/reference.wav"),
            patch("app.main.settings.HUGBACK_VOICE_CONSENT_PATH", "/nonexistent/consent.wav"),
        ):
            replacement.start()
            self.addCleanup(replacement.stop)
        google_client_patch = patch(
            "app.main.create_genai_client",
            side_effect=AssertionError("A real Google connection is forbidden in tests"),
        )
        self.google_client = google_client_patch.start()
        self.addCleanup(google_client_patch.stop)

    def test_app_starts_and_health_is_available_without_cloud_services(self):
        with TestClient(app) as client:
            response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")
        self.assertFalse(response.json()["memory_operational"])
        self.assertFalse(response.json()["firestore_operational"])
        self.google_client.assert_not_called()

    def test_websocket_rejects_unauthenticated_input_before_google(self):
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as websocket:
                websocket.send_json({"type": "ping"})
                self.assertEqual(websocket.receive_json()["type"], "error")
                with self.assertRaises(WebSocketDisconnect) as closed:
                    websocket.receive_json()
                self.assertEqual(closed.exception.code, 1008)
        self.google_client.assert_not_called()

    def test_websocket_rejects_incomplete_voice_before_google(self):
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as websocket:
                websocket.send_json(
                    {
                        "type": "authenticate",
                        "userId": "local-test-user",
                        "voiceSampleAudio": "invalid",
                    }
                )
                self.assertEqual(websocket.receive_json()["type"], "error")
                with self.assertRaises(WebSocketDisconnect) as closed:
                    websocket.receive_json()
                self.assertEqual(closed.exception.code, 1008)
        self.google_client.assert_not_called()

    def test_default_voice_ready_and_ping_with_mock_live_provider(self):
        configurations = []

        class FakeLiveSession:
            async def receive(self):
                # Stay connected until the browser disconnects and cancels us.
                await asyncio.Event().wait()
                yield None

        @asynccontextmanager
        async def connect(*, model, config):
            configurations.append(config)
            yield FakeLiveSession()

        fake_client = SimpleNamespace(
            aio=SimpleNamespace(live=SimpleNamespace(connect=connect))
        )
        with (
            patch("app.main.create_genai_client", return_value=fake_client),
            TestClient(app) as client,
        ):
            with client.websocket_connect("/ws") as websocket:
                websocket.send_json(
                    {"type": "authenticate", "userId": "local-test-user"}
                )
                ready = websocket.receive_json()
                self.assertEqual(ready["type"], "ready")
                self.assertEqual(ready["voice"], "default")
                self.assertEqual(ready["voiceName"], "Aoede")
                self.assertEqual(ready["voiceStatus"], "preset_configured")
                self.assertTrue(ready["sessionId"].startswith("session-"))
                websocket.send_json({"type": "ping"})
                self.assertEqual(websocket.receive_json(), {"type": "pong"})
        self.assertEqual(len(configurations), 1)
        self.assertIsNotNone(
            configurations[0].speech_config.voice_config.prebuilt_voice_config
        )
        self.google_client.assert_not_called()

    def test_preset_rejects_complete_browser_enrollment_before_google(self):
        with TestClient(app) as client, client.websocket_connect("/ws") as websocket:
            websocket.send_json(synthetic_voice_message())
            self.assertEqual(websocket.receive_json()["code"], "voice_selection_rejected")
            with self.assertRaises(WebSocketDisconnect):
                websocket.receive_json()
        self.google_client.assert_not_called()

    def test_experimental_mode_missing_recordings_does_not_fall_back(self):
        with (
            patch("app.main.settings.HUGBACK_LIVE_VOICE_MODE", "experimental-inline"),
            TestClient(app) as client,
            client.websocket_connect("/ws") as websocket,
        ):
            websocket.send_json({"type": "authenticate", "userId": "local-test-user"})
            error = websocket.receive_json()
            self.assertEqual(error["code"], "voice_selection_rejected")
            self.assertIn("fallback is disabled", error["message"])
        self.google_client.assert_not_called()

    def test_experimental_consent_gate_runs_before_ready_or_audio(self):
        for signature in (None, "", "synthetic-private-signature"):
            with self.subTest(acknowledged=bool(signature)):
                class FakeLiveSession:
                    setup_complete = types.LiveServerSetupComplete(
                        voice_consent_signature=types.VoiceConsentSignature(signature=signature)
                    )
                    send_realtime_input = AsyncMock()

                    async def receive(self):
                        await asyncio.Event().wait()
                        yield None

                session = FakeLiveSession()
                configurations = []

                @asynccontextmanager
                async def connect(*, model, config):
                    configurations.append(config)
                    yield session

                fake_client = SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))
                with (
                    patch("app.main.settings.HUGBACK_LIVE_VOICE_MODE", "experimental-inline"),
                    patch("app.main.create_genai_client", return_value=fake_client),
                    self.assertLogs("hugback.broker", level="INFO") as logs,
                    TestClient(app) as client,
                    client.websocket_connect("/ws") as websocket,
                ):
                    websocket.send_json(synthetic_voice_message())
                    response = websocket.receive_json()
                    if signature:
                        self.assertEqual(response["voice"], "experimental-inline")
                        self.assertEqual(response["voiceStatus"], "consent_acknowledged_likeness_unverified")
                        self.assertIsNone(response["voiceName"])
                        self.assertNotIn(signature, str(response))
                    else:
                        self.assertEqual(response["code"], "voice_consent_unverified")
                        with self.assertRaises(WebSocketDisconnect):
                            websocket.receive_json()
                self.assertNotIn("synthetic-private-signature", str(logs.output))
                session.send_realtime_input.assert_not_awaited()
                self.assertEqual(len(configurations), 1)
                self.assertIsNone(configurations[0].speech_config.voice_config.prebuilt_voice_config)

    def test_multiple_turns_and_interruption_reuse_one_voice_configuration(self):
        configurations = []

        class FakeLiveSession:
            turns = 0

            async def receive(self):
                if self.turns == 3:
                    await asyncio.Event().wait()
                self.turns += 1
                if self.turns == 2:
                    yield types.LiveServerMessage(
                        server_content=types.LiveServerContent(interrupted=True)
                    )
                yield types.LiveServerMessage(server_content=types.LiveServerContent(
                    input_transcription=types.Transcription(text="Hello"),
                ))
                yield types.LiveServerMessage(server_content=types.LiveServerContent(
                    model_turn=types.Content(parts=[types.Part(inline_data=types.Blob(
                        data=b"\0\0" * 24, mime_type="audio/pcm;rate=24000",
                    ))]),
                    turn_complete=True,
                ))

        @asynccontextmanager
        async def connect(*, model, config):
            configurations.append(config)
            yield FakeLiveSession()

        fake_client = SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))
        with patch("app.main.create_genai_client", return_value=fake_client), TestClient(app) as client:
            with client.websocket_connect("/ws") as websocket:
                websocket.send_json({"type": "authenticate", "userId": "local-test-user"})
                self.assertEqual(websocket.receive_json()["voiceName"], "Aoede")
                completed = 0
                interrupted = False
                while completed < 3:
                    event = websocket.receive_json()
                    completed += bool(event.get("turnComplete"))
                    interrupted |= bool(event.get("interrupted"))
                self.assertTrue(interrupted)
        self.assertEqual(len(configurations), 1)
        self.assertEqual(configurations[0].speech_config.voice_config.prebuilt_voice_config.voice_name, "Aoede")

    def test_show_character_facts_are_replaced_before_preset_audio_playback(self):
        class FakeLiveSession:
            def __init__(self):
                self.queue = asyncio.Queue()

            async def send_client_content(self, **kwargs):
                text = kwargs["turns"].parts[0].text
                if "Taarak" in text:
                    await self.queue.put(types.LiveServerMessage(server_content=types.LiveServerContent(
                        input_transcription=types.Transcription(text=text),
                    )))
                    await self.queue.put(types.LiveServerMessage(server_content=types.LiveServerContent(
                        model_turn=types.Content(parts=[types.Part(inline_data=types.Blob(
                            data=b"CHAT", mime_type="audio/pcm;rate=24000",
                        ))]),
                        output_transcription=types.Transcription(text="Achha, TV dekh rahe the."),
                        turn_complete=True,
                    )))
                else:
                    # Simulate provider audio arriving before finalized input words.
                    await self.queue.put(types.LiveServerMessage(server_content=types.LiveServerContent(
                        model_turn=types.Content(parts=[types.Part(inline_data=types.Blob(
                            data=b"FACT", mime_type="audio/pcm;rate=24000",
                        ))]),
                    )))
                    await self.queue.put(types.LiveServerMessage(server_content=types.LiveServerContent(
                        input_transcription=types.Transcription(text="Haan, kuch batana yaar."),
                    )))
                    await self.queue.put(types.LiveServerMessage(server_content=types.LiveServerContent(
                        model_turn=types.Content(parts=[types.Part(inline_data=types.Blob(
                            data=b"MORE", mime_type="audio/pcm;rate=24000",
                        ))]),
                    )))
                    await self.queue.put(types.LiveServerMessage(server_content=types.LiveServerContent(
                        input_transcription=types.Transcription(text=text),
                    )))
                    await self.queue.put(types.LiveServerMessage(server_content=types.LiveServerContent(
                        output_transcription=types.Transcription(text="Jethalal aur Daya Ben."),
                        turn_complete=True,
                    )))

            async def receive(self):
                while True:
                    event = await self.queue.get()
                    yield event
                    if event.server_content.turn_complete:
                        return

        @asynccontextmanager
        async def connect(*, model, config):
            yield FakeLiveSession()

        async def safe_tts(*args, **kwargs):
            self.assertEqual(kwargs["voice_key"], "Aoede")
            yield SimpleNamespace(pcm=b"SAFE", sample_rate=24000)

        fake_client = SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))
        with (
            patch("app.main.create_genai_client", return_value=fake_client),
            patch("app.voice.playback.stream_replicated_speech", safe_tts),
            TestClient(app) as client,
        ):
            with client.websocket_connect("/ws") as websocket:
                websocket.send_json({"type": "authenticate", "userId": "local-test-user"})
                self.assertEqual(websocket.receive_json()["voiceName"], "Aoede")
                websocket.send_json({"type": "text", "text": "Aaj Taarak Mehta dekh raha tha."})
                first = []
                while True:
                    event = websocket.receive_json()
                    first.append(event)
                    if event.get("turnComplete"):
                        break
                self.assertTrue(any("content" in event for event in first))
                websocket.send_json({"type": "text", "text": "Iske kirdaar ke baare mein tumhe pata hai kya?"})
                second = []
                while True:
                    event = websocket.receive_json()
                    second.append(event)
                    if event.get("turnComplete"):
                        break
                audio = [base64.b64decode(event["content"]["parts"][0]["inlineData"]["data"])
                         for event in second if "content" in event]
                captions = [event["outputTranscription"]["text"] for event in second
                            if "outputTranscription" in event]
                self.assertEqual(audio, [b"SAFE"])
                self.assertTrue(any("facts" in text for text in captions))
                self.assertFalse(any("Jethalal" in text for text in captions))

    def test_direct_first_turn_show_question_discards_early_live_audio(self):
        class FakeLiveSession:
            def __init__(self):
                self.ready = asyncio.Event()

            async def send_client_content(self, **kwargs):
                self.text = kwargs["turns"].parts[0].text
                self.ready.set()

            async def receive(self):
                await self.ready.wait()
                yield types.LiveServerMessage(server_content=types.LiveServerContent(
                    model_turn=types.Content(parts=[types.Part(inline_data=types.Blob(
                        data=b"UNSAFE", mime_type="audio/pcm;rate=24000",
                    ))]),
                    output_transcription=types.Transcription(text="It has famous characters."),
                ))
                yield types.LiveServerMessage(server_content=types.LiveServerContent(
                    input_transcription=types.Transcription(text=self.text),
                    turn_complete=True,
                ))

        @asynccontextmanager
        async def connect(*, model, config):
            yield FakeLiveSession()

        async def safe_tts(*args, **kwargs):
            self.assertEqual(kwargs["voice_key"], "Aoede")
            yield SimpleNamespace(pcm=b"SAFE", sample_rate=24000)

        fake_client = SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))
        with (
            patch("app.main.create_genai_client", return_value=fake_client),
            patch("app.voice.playback.stream_replicated_speech", safe_tts),
            TestClient(app) as client,
        ):
            with client.websocket_connect("/ws") as websocket:
                websocket.send_json({"type": "authenticate", "userId": "local-test-user"})
                self.assertEqual(websocket.receive_json()["type"], "ready")
                websocket.send_json({"type": "text", "text": "Do you know this TV show?"})
                events = []
                while True:
                    event = websocket.receive_json()
                    events.append(event)
                    if event.get("turnComplete"):
                        break
                audio = [base64.b64decode(event["content"]["parts"][0]["inlineData"]["data"])
                         for event in events if "content" in event]
                self.assertEqual(audio, [b"SAFE"])
                self.assertNotIn("famous characters", str(events))


if __name__ == "__main__":
    unittest.main()
