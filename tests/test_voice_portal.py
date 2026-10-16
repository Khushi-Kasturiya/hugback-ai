"""Owner-scoped portal enrollment with synthetic WAVs and no provider network."""
import asyncio
import base64
from contextlib import asynccontextmanager
from datetime import timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from google.genai import types

from app.config import settings
from app.main import app
from app.demo.models import CreateFamily, SelectRecipientVoice
from app.demo.store import DemoStore
from app.voice.profiles import VoiceProfileStore, now
from app.voice.service import SynthesizedAudio, VoiceEnrollmentError
from app.voice.playback import ReplicatedPlayback
from test_voice_tts import make_wav

ORIGIN = "http://127.0.0.1:3000"
HEADERS = {"Origin": ORIGIN, "X-Hugback-Development-User": "synthetic-voice-owner"}


def enrollment():
    return {
        "voiceSampleAudio": base64.b64encode(make_wav()).decode(),
        "consentAudio": base64.b64encode(make_wav(duration=2)).decode(),
        "adultOwnVoice": True, "consentToGoogleAndBilling": True,
    }


class PortalVoiceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "voice.sqlite3"
        self.store = VoiceProfileStore(self.path)
        for field, value in {
            "HUGBACK_AUTH_MODE": "development", "HUGBACK_LIVE_VOICE_MODE": "preset",
            "HUGBACK_REPLICATED_TTS_ENABLED": True, "HUGBACK_VOICE_DB_PATH": self.path,
            "GEMINI_API_KEY": "synthetic-not-a-real-key", "LOCAL_DEMO_ENABLED": True,
            "LOCAL_DEMO_DB_PATH": Path(temp.name) / "demo.sqlite3",
            "FIRESTORE_ENABLED": False, "MEMORY_ENABLED": False, "FOLLOWUPS_ENABLED": False,
        }.items():
            item = patch.object(settings, field, value)
            item.start(); self.addCleanup(item.stop)
        self.provider = patch("app.voice.routes.provision_voice", new_callable=AsyncMock).start()
        self.addCleanup(patch.stopall)
        self.provider.return_value = SimpleNamespace(key="voicekey_synthetic", expire_time=now() + timedelta(days=2))
        self.client = TestClient(app, client=("127.0.0.1", 12345))

    def create_profile(self):
        result = self.client.post("/api/voice/enroll", headers=HEADERS, json=enrollment())
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()["profile"]

    def test_enroll_metadata_only_disabled_until_explicit_selection(self):
        profile = self.create_profile()
        self.assertFalse(profile["enabled"])
        self.assertEqual(profile["expirySource"], "provider")
        self.assertNotIn("voicekey", json.dumps(profile))
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(len(conn.execute("PRAGMA table_info(voices)").fetchall()), 7)
        chosen = self.client.put("/api/voice/profile", headers=HEADERS,
                                 json={"profileId": profile["id"], "enabled": True})
        self.assertTrue(chosen.json()["profile"]["enabled"])
        status = self.client.get("/api/portal/status", headers=HEADERS).json()
        self.assertEqual(status["voice"]["profile"]["id"], profile["id"])
        self.assertNotIn("voicekey", json.dumps(status))
        self.assertEqual(chosen.headers["cache-control"], "no-store")
        self.provider.assert_awaited_once()
        restarted = VoiceProfileStore(self.path)
        self.assertEqual(restarted.resolve("synthetic-voice-owner", profile["id"]), "voicekey_synthetic")

    def test_short_lived_audio_estimate_is_cleared_and_ignored(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute("CREATE TABLE voices (owner TEXT PRIMARY KEY, profile_id TEXT NOT NULL, "
                         "voice_key TEXT, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, "
                         "enabled INTEGER NOT NULL, expiry_source TEXT NOT NULL, "
                         "speaking_form TEXT NOT NULL DEFAULT 'unavailable')")
            conn.execute("INSERT INTO voices VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
                "synthetic-voice-owner", "a" * 32, "voicekey_synthetic",
                now().isoformat(), (now() + timedelta(days=1)).isoformat(),
                1, "provider", "masculine",
            ))
        profile = self.store.get("synthetic-voice-owner")
        self.assertNotIn("speakingForm", profile)
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute("SELECT speaking_form FROM voices").fetchone()[0], "unavailable")
        replacement = self.store.save("synthetic-voice-owner", "voicekey_replacement")
        self.assertNotIn("speakingForm", replacement)

    def test_other_owner_cannot_read_select_or_delete_profile(self):
        profile = self.create_profile()
        other = {**HEADERS, "X-Hugback-Development-User": "synthetic-other-owner"}
        self.assertIsNone(self.client.get("/api/voice/profile", headers=other).json()["profile"])
        self.assertEqual(self.client.put("/api/voice/profile", headers=other,
                         json={"profileId": profile["id"], "enabled": True}).status_code, 409)
        self.client.delete("/api/voice/profile", headers=other)
        self.assertIsNotNone(self.store.get("synthetic-voice-owner"))

    def test_expired_enabled_profile_does_not_silently_become_preset(self):
        profile = self.create_profile()
        self.store.select("synthetic-voice-owner", profile["id"], True)
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE voices SET expires_at=?", ((now() - timedelta(seconds=1)).isoformat(),))
        expired = self.store.get("synthetic-voice-owner")
        self.assertTrue(expired["expired"])
        self.assertTrue(expired["enabled"])
        with self.assertRaises(VoiceEnrollmentError):
            self.store.resolve("synthetic-voice-owner", profile["id"])
        with sqlite3.connect(self.path) as conn:
            self.assertIsNone(conn.execute("SELECT voice_key FROM voices").fetchone()[0])
        self.assertFalse(self.store.select("synthetic-voice-owner", profile["id"], False)["enabled"])

    def test_replacement_invalidates_old_profile_and_requires_reselection(self):
        first = self.create_profile()
        self.store.select("synthetic-voice-owner", first["id"], True)
        second = self.create_profile()
        self.assertNotEqual(first["id"], second["id"])
        self.assertFalse(second["enabled"])
        with self.assertRaises(VoiceEnrollmentError):
            self.store.resolve("synthetic-voice-owner", first["id"])

    def test_disabled_feature_denies_provider_but_allows_removal(self):
        self.create_profile(); self.provider.reset_mock()
        with patch.object(settings, "HUGBACK_REPLICATED_TTS_ENABLED", False):
            self.assertEqual(self.client.post("/api/voice/enroll", headers=HEADERS, json=enrollment()).status_code, 403)
            self.assertEqual(self.client.delete("/api/voice/profile", headers=HEADERS).status_code, 200)
        self.provider.assert_not_called()
        self.assertIsNone(self.store.get("synthetic-voice-owner"))

    def test_origin_peer_auth_and_consent_gates_precede_google(self):
        body = enrollment()
        for change in ({"adultOwnVoice": False}, {"consentToGoogleAndBilling": False},
                       {"parentId": "other-parent"}, {"consentAudio": "invalid"}):
            response = self.client.post("/api/voice/enroll", headers=HEADERS, json={**body, **change})
            self.assertIn(response.status_code, (400, 422))
            self.assertNotIn(body["voiceSampleAudio"], response.text)
        for headers in ({}, {**HEADERS, "Origin": "https://evil.example"},
                        {"X-Hugback-Development-User": "synthetic-voice-owner"}):
            self.assertIn(self.client.post("/api/voice/enroll", headers=headers, json=body).status_code, (401, 403))
        remote = TestClient(app, client=("203.0.113.1", 1234))
        self.assertEqual(remote.post("/api/voice/enroll", headers={**HEADERS, "X-Forwarded-For": "127.0.0.1"}, json=body).status_code, 403)
        self.provider.assert_not_called()

    def test_provider_failure_is_redacted_not_misdiagnosed_or_retried(self):
        self.provider.side_effect = RuntimeError("PERMISSION_DENIED voicekey_private audio-private")
        response = self.client.post("/api/voice/enroll", headers=HEADERS, json=enrollment())
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private", response.text)
        self.assertNotIn("Paid Tier 1", response.text)
        self.provider.assert_awaited_once()
        self.assertIsNone(self.store.get("synthetic-voice-owner"))

    def test_known_provider_status_is_safe_and_actionable(self):
        from app.voice.routes import VoiceProvisionFailure
        self.provider.side_effect = VoiceProvisionFailure(status_code=403)
        response = self.client.post("/api/voice/enroll", headers=HEADERS, json=enrollment())
        self.assertEqual(response.status_code, 502)
        self.assertIn("HTTP 403", response.text)
        self.assertIn("project access", response.text)
        self.provider.assert_awaited_once()

    def test_local_save_failure_is_not_reported_as_google_rejection(self):
        with patch("app.voice.routes.get_voice_store") as get_store:
            get_store.return_value.save.side_effect = OSError("private local path")
            response = self.client.post("/api/voice/enroll", headers=HEADERS, json=enrollment())
        self.assertEqual(response.status_code, 500)
        self.assertIn("local voice setup", response.text)
        self.assertNotIn("private local path", response.text)
        self.provider.assert_awaited_once()


    def test_pending_upload_blocks_duplicate_mutations(self):
        with patch("app.voice.routes._enrolling", {"synthetic-voice-owner"}):
            self.assertTrue(self.client.get("/api/voice/profile", headers=HEADERS).json()["enrolling"])
            self.assertEqual(self.client.post("/api/voice/enroll", headers=HEADERS, json=enrollment()).status_code, 409)
            self.assertEqual(self.client.delete("/api/voice/profile", headers=HEADERS).status_code, 409)
        self.provider.assert_not_called()

    def test_websocket_rejects_foreign_raw_disabled_and_omitted_selection_before_google(self):
        profile = self.create_profile()
        self.store.select("synthetic-voice-owner", profile["id"], True)
        for change in ({"voiceKey": "voicekey_synthetic"}, {"voiceProfileId": "other-profile"},
                       {"userId": "synthetic-other-owner", "voiceProfileId": profile["id"]}, {}):
            with patch("app.main.create_genai_client") as google:
                with self.client.websocket_connect("/ws", headers={"Origin": ORIGIN}) as ws:
                    ws.send_json({"type": "authenticate", "userId": "synthetic-voice-owner", **change})
                    self.assertEqual(ws.receive_json()["code"], "voice_selection_rejected")
                google.assert_not_called()

    def test_demo_uses_child_owned_voice_but_parent_memory_and_only_custom_audio(self):
        profile = self.create_profile()
        self.store.select("synthetic-voice-owner", profile["id"], True)
        family = DemoStore(settings.LOCAL_DEMO_DB_PATH).create("synthetic-voice-owner", CreateFamily(
            syntheticOnly=True, simulateChildConsent=True, simulateParentConsent=True,
            enableMemory=False, childGender="male",
        ))
        recipient = family["recipients"][0]
        # Real replacement handoff: enabling the new profile cannot mutate any
        # recipient's assignment, and the old pinned profile cannot fall back.
        other = self.client.post("/api/demo/recipients", headers=HEADERS, json={
            "syntheticOnly": True, "simulateChildConsent": True, "simulateParentConsent": True,
            "label": "Father", "relationship": "father",
        })
        self.assertEqual(other.status_code, 200)
        family = DemoStore(settings.LOCAL_DEMO_DB_PATH).select_voice("synthetic-voice-owner", SelectRecipientVoice(
            syntheticOnly=True, recipientId=recipient["recipientId"], revision=0, mode="child", profileId=profile["id"],
        ))
        recipient = family["recipients"][0]
        old_profile = profile
        self.provider.return_value = SimpleNamespace(key="voicekey_synthetic_replacement", expire_time=now()+timedelta(days=2))
        profile = self.create_profile()
        with patch("app.main.create_genai_client") as google:
            with self.client.websocket_connect("/ws", headers={"Origin": ORIGIN}) as ws:
                ws.send_json({"type": "authenticate", "userId": "synthetic-voice-owner",
                    "demoParent": True, "demoRecipientId": recipient["recipientId"],
                    "demoRecipientRevision": recipient["revision"], "voiceProfileId": old_profile["id"]})
                self.assertEqual(ws.receive_json()["code"], "voice_selection_rejected")
            google.assert_not_called()
        self.assertEqual(self.client.put("/api/voice/profile", headers=HEADERS,
            json={"profileId": profile["id"], "enabled": True}).status_code, 200)
        assigned = self.client.put("/api/demo/recipient-voice", headers=HEADERS, json={
            "syntheticOnly": True, "recipientId": recipient["recipientId"], "revision": recipient["revision"],
            "mode": "child", "profileId": profile["id"],
        })
        self.assertEqual(assigned.status_code, 200)
        recipient = assigned.json()["recipients"][0]
        self.assertEqual(assigned.json()["recipients"][1]["voice"]["mode"], "standard")
        coordinator = SimpleNamespace(begin=AsyncMock(side_effect=RuntimeError("memory off")))
        class Live:
            def __init__(self): self.queue = asyncio.Queue()
            async def send_client_content(self, **kwargs):
                await self.queue.put(types.LiveServerMessage(server_content=types.LiveServerContent(
                    interrupted=True,
                    model_turn=types.Content(parts=[types.Part(inline_data=types.Blob(data=b"STALE", mime_type="audio/pcm"))]),
                    output_transcription=types.Transcription(text="Stale interrupted output."),
                )))
                for text in ("Hello, I am Hugback AI.", "A second sentence."):
                    await self.queue.put(types.LiveServerMessage(server_content=types.LiveServerContent(
                        model_turn=types.Content(parts=[
                            types.Part(inline_data=types.Blob(data=b"PRESET", mime_type="audio/pcm")),
                            types.Part(text="Unspoken Live draft must not be shown."),
                        ]),
                        output_transcription=types.Transcription(text=text), turn_complete=True,
                    )))
            async def receive(self): yield await self.queue.get()
        @asynccontextmanager
        async def connect(**kwargs):
            self.assertIn("main theek lagta hoon", kwargs["config"].system_instruction.parts[0].text)
            yield Live()
        async def synthesize(*args, **kwargs):
            self.assertEqual(kwargs["voice_key"], "voicekey_synthetic_replacement")
            self.assertNotIn("Stale", kwargs["text"])
            await asyncio.sleep(0.01)
            yield SynthesizedAudio(pcm=b"CUSTOM", sample_rate=24000)
        with (
            patch("app.main.create_genai_client", return_value=SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))),
            patch("app.main.get_demo_coordinator", return_value=coordinator),
            patch("app.voice.playback.stream_replicated_speech", synthesize),
            patch("app.main.get_session_store", side_effect=AssertionError("No cloud writes")),
            self.client.websocket_connect("/ws", headers={"Origin": ORIGIN}) as ws,
        ):
            ws.send_json({"type": "authenticate", "userId": "synthetic-voice-owner", "demoParent": True, "demoRecipientId": recipient["recipientId"], "demoRecipientRevision": recipient["revision"], "voiceProfileId": profile["id"]})
            ready = ws.receive_json()
            self.assertEqual(ready["voice"], "replicated")
            self.assertEqual(ready["demo"]["parentId"], recipient["recipientId"])
            ws.send_json({"type": "text", "text": "Hello from a synthetic caller."})
            audio = []; turns = 0; subtitles = []
            while turns < 2:
                event = ws.receive_json()
                if "outputTranscription" in event:
                    self.assertIn("content", event)
                    self.assertTrue(event["outputTranscription"]["playbackAligned"])
                    subtitles.append(event["outputTranscription"]["text"])
                if "content" in event:
                    audio.append(base64.b64decode(event["content"]["parts"][0]["inlineData"]["data"]))
                if event.get("turnComplete"): turns += 1
            self.assertEqual(audio, [b"CUSTOM", b"CUSTOM"])
            self.assertEqual(subtitles, ["Hello, I am Hugback AI.",
                                         "Sorry, I missed that. Could you say it again?"])
        self.assertEqual(coordinator.begin.await_args.args[0], recipient["recipientId"])

    def test_broker_starts_first_phrase_before_live_turn_end_and_resets_after_interrupt(self):
        profile = self.create_profile()
        self.store.select("synthetic-voice-owner", profile["id"], True)
        store = DemoStore(settings.LOCAL_DEMO_DB_PATH)
        family = store.create("synthetic-voice-owner", CreateFamily(
            syntheticOnly=True, simulateChildConsent=True, simulateParentConsent=True, enableMemory=False,
        ))
        recipient = family["recipients"][0]
        recipient = store.select_voice("synthetic-voice-owner", SelectRecipientVoice(
            syntheticOnly=True, recipientId=recipient["recipientId"], revision=recipient["revision"],
            mode="child", profileId=profile["id"],
        ))["recipients"][0]
        prefix = "It is really good to hear from you,"
        requests = []

        class Live:
            def __init__(self):
                self.queue = asyncio.Queue()
            async def send_client_content(self, **kwargs):
                command = kwargs["turns"].parts[0].text
                if command == "interrupt":
                    content = types.LiveServerContent(interrupted=True)
                elif command == "finish":
                    content = types.LiveServerContent(
                        output_transcription=types.Transcription(text=" a synthetic sentence."), turn_complete=True,
                    )
                else:
                    # No end-of-turn/sentence: the client deliberately waits for
                    # the first custom PCM before allowing the turn to finish.
                    content = types.LiveServerContent(
                        output_transcription=types.Transcription(text=prefix + " and this is"),
                    )
                await self.queue.put(types.LiveServerMessage(server_content=content))
            async def receive(self):
                yield await self.queue.get()

        @asynccontextmanager
        async def connect(**kwargs):
            yield Live()
        async def synthesize(*args, **kwargs):
            requests.append(kwargs["text"])
            yield SynthesizedAudio(pcm=b"CUSTOM", sample_rate=24000)

        with (
            patch("app.main.create_genai_client", return_value=SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))),
            patch("app.main.get_demo_coordinator", return_value=SimpleNamespace(begin=AsyncMock(side_effect=RuntimeError("memory off")))),
            patch("app.voice.playback.stream_replicated_speech", synthesize),
            patch("app.main.get_session_store", side_effect=AssertionError("No cloud writes")),
            self.client.websocket_connect("/ws", headers={"Origin": ORIGIN}) as ws,
        ):
            ws.send_json({"type": "authenticate", "userId": "synthetic-voice-owner", "demoParent": True,
                          "demoRecipientId": recipient["recipientId"], "demoRecipientRevision": recipient["revision"],
                          "voiceProfileId": profile["id"]})
            self.assertEqual(ws.receive_json()["voice"], "replicated")
            # Strict scope checking holds even child-voice text until the
            # caller's turn is complete. An interruption discards the draft.
            ws.send_json({"type": "text", "text": "start"})
            ws.send_json({"type": "text", "text": "interrupt"})
            self.assertTrue(ws.receive_json()["interrupted"])
            ws.send_json({"type": "text", "text": "start"})
            ws.send_json({"type": "text", "text": "finish"})
            captions = []
            while True:
                event = ws.receive_json()
                if "outputTranscription" in event:
                    self.assertEqual(base64.b64decode(event["content"]["parts"][0]["inlineData"]["data"]), b"CUSTOM")
                    captions.append(event["outputTranscription"]["text"])
                if event.get("turnComplete"):
                    break
            self.assertEqual(captions, [prefix, "and this is a synthetic sentence."])
            self.assertEqual(requests, captions)


class PlaybackTests(unittest.IsolatedAsyncioTestCase):
    async def test_interruption_cancels_old_provider_stream_and_preserves_next_turn(self):
        started, cancelled, completed = asyncio.Event(), asyncio.Event(), asyncio.Event()
        events = []
        async def send(value):
            event = json.loads(value); events.append(event)
            if event.get("turnComplete"): completed.set()
        async def stream(*args, **kwargs):
            if kwargs["text"] == "old":
                started.set()
                try: await asyncio.Event().wait()
                finally: cancelled.set()
            yield SynthesizedAudio(pcm=(kwargs["text"] + " ").encode(), sample_rate=24000)
        with patch("app.voice.playback.stream_replicated_speech", stream):
            playback = ReplicatedPlayback(None, SimpleNamespace(send_text=send), voice_key="voicekey_test", model="synthetic")
            try:
                playback.enqueue("old", final=True)
                await asyncio.wait_for(started.wait(), 1)
                playback.interrupt(); playback.enqueue("new", final=True)
                await asyncio.wait_for(completed.wait(), 1)
                self.assertTrue(cancelled.is_set())
                self.assertEqual(len(events), 2)
                self.assertEqual(base64.b64decode(events[0]["content"]["parts"][0]["inlineData"]["data"]), b"new ")
                self.assertEqual(events[0]["outputTranscription"]["text"], "new")
            finally: await playback.close()
            self.assertTrue(playback.task.done())

    async def test_failure_stops_without_preset_or_sensitive_error(self):
        websocket = SimpleNamespace(send_text=AsyncMock())
        async def stream(*args, **kwargs):
            raise RuntimeError("secret-voice-key")
            yield
        with patch("app.voice.playback.stream_replicated_speech", stream):
            playback = ReplicatedPlayback(None, websocket, voice_key="voicekey_test", model="synthetic")
            playback.enqueue("test", final=True)
            await asyncio.wait_for(playback.task, 1)
            event = json.loads(websocket.send_text.await_args.args[0])
            self.assertEqual(event["code"], "replicated_tts_failed")
            self.assertNotIn("outputTranscription", event)
            self.assertNotIn("secret", json.dumps(event))
            with self.assertRaises(RuntimeError): playback.enqueue("no fallback")
            await playback.close()

    async def test_checkpoint_only_after_custom_audio_and_no_audio_is_failure(self):
        checkpoint = AsyncMock()
        async def empty(*args, **kwargs):
            if False: yield
        websocket = SimpleNamespace(send_text=AsyncMock())
        with patch("app.voice.playback.stream_replicated_speech", empty):
            playback = ReplicatedPlayback(None, websocket, voice_key="voicekey_test", model="synthetic", on_audio=checkpoint)
            playback.enqueue("nothing", final=True)
            await asyncio.wait_for(playback.task, 1)
            checkpoint.assert_not_awaited()
            self.assertEqual(json.loads(websocket.send_text.await_args.args[0])["type"], "error")
            await playback.close()

    async def test_pending_speech_queue_is_bounded(self):
        websocket = SimpleNamespace(send_text=AsyncMock())
        playback = ReplicatedPlayback(None, websocket, voice_key="voicekey_test", model="synthetic")
        try:
            for _ in range(32): playback.enqueue("test")
            with self.assertRaises(asyncio.QueueFull): playback.enqueue("overflow")
        finally: await playback.close()

    async def test_checkpoint_follows_first_emitted_chunk_not_text(self):
        events, order = [], []
        finished = asyncio.Event()
        async def send(value):
            event = json.loads(value); events.append(event)
            order.append("complete" if event.get("turnComplete") else "audio")
            if event.get("turnComplete"): finished.set()
        async def checkpoint():
            order.append("checkpoint")
        async def stream(*args, **kwargs):
            yield SynthesizedAudio(pcm=b"one1", sample_rate=24000)
            yield SynthesizedAudio(pcm=b"two2", sample_rate=24000)
        with patch("app.voice.playback.stream_replicated_speech", stream):
            playback = ReplicatedPlayback(None, SimpleNamespace(send_text=send),
                                          voice_key="voicekey_test", model="synthetic", on_audio=checkpoint)
            try:
                playback.enqueue("hello", final=True)
                await asyncio.wait_for(finished.wait(), 1)
                await asyncio.sleep(0)  # Checkpoint is deliberately off the PCM path.
                self.assertEqual(order.count("checkpoint"), 1)
                self.assertGreater(order.index("checkpoint"), order.index("audio"))
                self.assertEqual([item for item in order if item != "checkpoint"], ["audio", "audio", "complete"])
                self.assertEqual(events[0]["outputTranscription"], {"text": "hello", "playbackAligned": True})
                self.assertNotIn("outputTranscription", events[1])
                self.assertNotIn("outputTranscription", events[2])
            finally: await playback.close()

    async def test_slow_tts_never_sends_caption_before_first_audio_chunk(self):
        started, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()
        events = []
        async def send(value):
            event = json.loads(value); events.append(event)
            if event.get("turnComplete"): finished.set()
        async def stream(*args, **kwargs):
            started.set()
            await release.wait()
            yield SynthesizedAudio(pcm=b"\0\0" * 128, sample_rate=24000)
        with patch("app.voice.playback.stream_replicated_speech", stream):
            playback = ReplicatedPlayback(None, SimpleNamespace(send_text=send),
                                          voice_key="voicekey_test", model="synthetic")
            try:
                playback.enqueue("Synthetic delayed phrase.", final=True)
                await asyncio.wait_for(started.wait(), 1)
                self.assertEqual(events, [])
                release.set()
                await asyncio.wait_for(finished.wait(), 1)
                self.assertEqual(len(events), 2)
                self.assertIn("content", events[0])
                self.assertEqual(events[0]["outputTranscription"]["text"], "Synthetic delayed phrase.")
            finally:
                await playback.close()

    async def test_close_racing_with_interruption_does_not_swallow_shutdown(self):
        started, released = asyncio.Event(), asyncio.Event()
        async def stream(*args, **kwargs):
            started.set()
            try: await asyncio.Event().wait()
            finally: released.set()
            yield
        with patch("app.voice.playback.stream_replicated_speech", stream):
            playback = ReplicatedPlayback(None, SimpleNamespace(send_text=AsyncMock()),
                                          voice_key="voicekey_test", model="synthetic")
            playback.enqueue("hello")
            await asyncio.wait_for(started.wait(), 1)
            playback.interrupt()
            await asyncio.wait_for(playback.close(), 1)
            self.assertTrue(released.is_set())

    async def test_timeout_closes_stream_and_stops_voice(self):
        released = asyncio.Event()
        async def stream(*args, **kwargs):
            try: await asyncio.Event().wait()
            finally: released.set()
            yield
        real_timeout = asyncio.timeout
        with (
            patch("app.voice.playback.stream_replicated_speech", stream),
            patch("app.voice.playback.asyncio.timeout", side_effect=lambda _: real_timeout(0.01)),
        ):
            websocket = SimpleNamespace(send_text=AsyncMock())
            playback = ReplicatedPlayback(None, websocket, voice_key="voicekey_test", model="synthetic")
            playback.enqueue("hello")
            await asyncio.wait_for(playback.task, 1)
            self.assertTrue(released.is_set())
            self.assertEqual(json.loads(websocket.send_text.await_args.args[0])["code"], "replicated_tts_failed")
            await playback.close()

class EnrollmentTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_sdk_serialization_and_single_send_use_only_mock_transport(self):
        import httpx
        from google import genai
        from app.voice.routes import provision_voice
        from app.voice.service import InlineVoice
        real_client = genai.Client
        calls = []

        def respond(request):
            calls.append(json.loads(request.content))
            self.assertEqual(request.url.path, "/v1beta/voices")
            return httpx.Response(200, json={
                "key": "voicekey_synthetic", "type": "replicated",
                "expire_time": (now() + timedelta(days=2)).isoformat(),
            })

        def factory(**kwargs):
            kwargs["http_options"]["async_client_args"]["transport"] = httpx.MockTransport(respond)
            return real_client(**kwargs)

        with patch("app.voice.routes.genai.Client", side_effect=factory), patch.object(settings, "GEMINI_API_KEY", "offline-placeholder"):
            result = await provision_voice(InlineVoice(sample=make_wav(), consent=make_wav(duration=2)))
        self.assertEqual(result.key, "voicekey_synthetic")
        self.assertEqual(len(calls), 1)
        self.assertFalse(calls[0]["store"])
        self.assertNotIn("model", calls[0]["voice"])
        self.assertEqual(base64.b64decode(calls[0]["voice"]["replicated"]["source_audio"]["data"]), make_wav())

    async def test_provider_retry_is_blocked_at_transport_boundary(self):
        import httpx
        from google import genai
        from app.voice.routes import VoiceProvisionFailure, provision_voice
        from app.voice.service import InlineVoice
        real_client = genai.Client
        requests = []
        def respond(request):
            requests.append(request.url.path)
            return httpx.Response(503, json={"error": {"code": 503, "message": "synthetic retryable failure"}})
        def factory(**kwargs):
            kwargs["http_options"]["async_client_args"]["transport"] = httpx.MockTransport(respond)
            return real_client(**kwargs)
        with patch("app.voice.routes.genai.Client", side_effect=factory), patch.object(settings, "GEMINI_API_KEY", "offline-placeholder"):
            with self.assertRaises(VoiceProvisionFailure) as failure:
                await provision_voice(InlineVoice(sample=make_wav(), consent=make_wav(duration=2)))
        self.assertEqual(requests, ["/v1beta/voices"])
        self.assertEqual(failure.exception.status_code, 503)
        self.assertFalse(failure.exception.repeated_send)

    async def test_first_non_retryable_provider_error_is_preserved_without_body(self):
        import httpx
        from google import genai
        from app.voice.routes import VoiceProvisionFailure, provision_voice
        from app.voice.service import InlineVoice
        real_client = genai.Client
        requests = []
        def respond(request):
            requests.append(request.url.path)
            return httpx.Response(403, json={"error": {"message": "private provider detail"}})
        def factory(**kwargs):
            kwargs["http_options"]["async_client_args"]["transport"] = httpx.MockTransport(respond)
            return real_client(**kwargs)
        with patch("app.voice.routes.genai.Client", side_effect=factory), patch.object(settings, "GEMINI_API_KEY", "offline-placeholder"):
            with self.assertRaises(VoiceProvisionFailure) as failure:
                await provision_voice(InlineVoice(sample=make_wav(), consent=make_wav(duration=2)))
        self.assertEqual(requests, ["/v1beta/voices"])
        self.assertEqual(failure.exception.status_code, 403)
        self.assertNotIn("private", str(failure.exception))
