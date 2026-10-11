import base64
import io
import unittest
import wave
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException

from app.agent.live_session import create_genai_client, create_live_config
from app.voice.routes import VoiceEnrollmentRequest, enroll_voice
from app.voice.service import (
    InlineVoice,
    VoiceEnrollmentError,
    create_replicated_voice_key,
    parse_inline_voice,
    parse_voice_key,
    split_ready_speech,
    stream_replicated_speech,
    synthesize_replicated_speech,
    validate_wav,
)


def make_wav(
    duration: float = 10.0,
    rate: int = 24_000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(sample_width)
        target.setframerate(rate)
        target.writeframes(b"\0" * int(duration * rate * channels * sample_width))
    return output.getvalue()


class VoiceValidationTests(unittest.TestCase):
    def test_replication_lets_google_select_model_and_uses_stateless_storage(self):
        client = Mock()
        client.voices.create.return_value = SimpleNamespace(key="voicekey_created")
        recordings = InlineVoice(sample=b"sample", consent=b"consent")

        key = create_replicated_voice_key(
            client,
            recordings,
        )

        self.assertEqual(key, "voicekey_created")
        request = client.voices.create.call_args.kwargs
        self.assertFalse(request["store"])
        self.assertNotIn("model", request["voice"])

    def test_accepts_gemini_ready_wav(self):
        recording = validate_wav(
            make_wav(), label="Voice sample", minimum_seconds=10
        )
        self.assertEqual(recording.duration_seconds, 10)

    def test_rejects_stereo_audio(self):
        with self.assertRaisesRegex(VoiceEnrollmentError, "mono"):
            validate_wav(
                make_wav(channels=2), label="Voice sample", minimum_seconds=10
            )

    def test_rejects_wrong_sample_rate(self):
        with self.assertRaisesRegex(VoiceEnrollmentError, "24 kHz"):
            validate_wav(
                make_wav(rate=44_100), label="Voice sample", minimum_seconds=10
            )

    def test_rejects_out_of_range_duration(self):
        with self.assertRaisesRegex(VoiceEnrollmentError, "10–30"):
            validate_wav(
                make_wav(duration=5), label="Voice sample", minimum_seconds=10
            )

    def test_parses_complete_inline_voice_envelope(self):
        sample = make_wav(duration=10)
        consent = make_wav(duration=2)
        voice = parse_inline_voice(
            {
                "voiceSampleAudio": base64.b64encode(sample).decode("ascii"),
                "consentAudio": base64.b64encode(consent).decode("ascii"),
            }
        )
        self.assertEqual(voice.sample, sample)
        self.assertEqual(voice.consent, consent)

    def test_rejects_short_consent_recording(self):
        with self.assertRaisesRegex(VoiceEnrollmentError, "2–30"):
            parse_inline_voice({
                "voiceSampleAudio": base64.b64encode(make_wav()).decode("ascii"),
                "consentAudio": base64.b64encode(make_wav(duration=1)).decode("ascii"),
            })

    def test_rejects_partial_inline_voice_envelope(self):
        with self.assertRaisesRegex(VoiceEnrollmentError, "Both"):
            parse_inline_voice({"voiceSampleAudio": "abc"})

    def test_accepts_google_voice_key(self):
        self.assertEqual(
            parse_voice_key({"voiceKey": "voicekey_test123"}),
            "voicekey_test123",
        )

    def test_rejects_non_google_voice_key(self):
        with self.assertRaisesRegex(VoiceEnrollmentError, "invalid"):
            parse_voice_key({"voiceKey": "Aoede"})


class ReplicatedSynthesisTests(unittest.IsolatedAsyncioTestCase):
    async def test_flash_lite_synthesizes_with_returned_voice_key(self):
        wav = make_wav(duration=1)
        client = Mock()
        client.aio.interactions.create = AsyncMock(
            return_value=SimpleNamespace(
                output_audio=SimpleNamespace(
                    data=base64.b64encode(wav).decode("ascii")
                )
            )
        )

        audio = await synthesize_replicated_speech(
            client,
            voice_key="voicekey_test123",
            text="Hello from Elara.",
            model="gemini-3.8-flash-lite-tts",
        )

        self.assertEqual(audio.sample_rate, 24_000)
        self.assertEqual(len(audio.pcm), 48_000)
        request = client.aio.interactions.create.await_args.kwargs
        self.assertEqual(request["api_version"], "v1beta")
        self.assertEqual(request["model"], "gemini-3.8-flash-lite-tts")
        self.assertEqual(
            request["generation_config"]["speech_config"][0]["voice"],
            "voicekey_test123",
        )

    async def test_streaming_tts_yields_raw_audio_deltas(self):
        events = [
            SimpleNamespace(event_type="interaction.created"),
            SimpleNamespace(
                event_type="step.delta",
                delta=SimpleNamespace(
                    type="audio",
                    data=base64.b64encode(b"pcm-one").decode("ascii"),
                    sample_rate=24_000,
                ),
            ),
            SimpleNamespace(
                event_type="step.delta",
                delta=SimpleNamespace(
                    type="audio",
                    data=base64.b64encode(b"pcm-two").decode("ascii"),
                    sample_rate=24_000,
                ),
            ),
        ]

        async def event_stream():
            for event in events:
                yield event

        client = Mock()
        client.aio.interactions.create = AsyncMock(return_value=event_stream())

        chunks = [
            chunk
            async for chunk in stream_replicated_speech(
                client,
                voice_key="voicekey_test123",
                text="Hello from Elara.",
                model="gemini-3.8-flash-lite-tts",
            )
        ]

        self.assertEqual([chunk.pcm for chunk in chunks], [b"pcm-one", b"pcm-two"])
        request = client.aio.interactions.create.await_args.kwargs
        self.assertTrue(request["stream"])
        self.assertFalse(request["store"])
        self.assertEqual(request["response_format"]["mime_type"], "audio/l16")


class StreamingSpeechSegmentationTests(unittest.TestCase):
    def test_releases_complete_sentence_and_keeps_partial_text(self):
        ready, pending = split_ready_speech(
            "I remember that. Let me think about your next"
        )
        self.assertEqual(ready, ["I remember that."])
        self.assertEqual(pending, "Let me think about your next")

    def test_final_flushes_short_unpunctuated_text(self):
        ready, pending = split_ready_speech("Of course", final=True)
        self.assertEqual(ready, ["Of course"])
        self.assertEqual(pending, "")

    def test_releases_punctuated_sentence_at_stream_boundary(self):
        ready, pending = split_ready_speech("I can help with that.")
        self.assertEqual(ready, ["I can help with that."])
        self.assertEqual(pending, "")

    def test_long_text_is_bounded_without_waiting_for_turn_end(self):
        ready, pending = split_ready_speech("word " * 80, maximum_chars=100)
        self.assertTrue(ready)
        self.assertTrue(all(len(segment) <= 100 for segment in ready))
        self.assertTrue(pending)


class LiveVoiceSelectionTests(unittest.TestCase):
    @patch("app.agent.live_session.genai.Client")
    def test_api_key_client_forces_developer_api_mode(self, client):
        create_genai_client()
        self.assertFalse(client.call_args.kwargs["vertexai"])

    def test_default_voice_remains_available(self):
        config = create_live_config()
        voice = config.speech_config.voice_config
        self.assertIsNotNone(voice.prebuilt_voice_config)
        self.assertIsNone(voice.voice)


class ReplicatedTTSGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_enrollment_gate_stops_before_authentication_or_provider_calls(self):
        with (
            patch("app.config.settings.ELARA_REPLICATED_TTS_ENABLED", False),
            patch("app.voice.routes.authenticate_http_headers") as authenticate,
            patch("app.voice.routes.provision_voice") as client,
        ):
            with self.assertRaises(HTTPException) as error:
                await enroll_voice(
                    VoiceEnrollmentRequest(
                        voiceSampleAudio="synthetic", consentAudio="synthetic",
                        adultOwnVoice=True, consentToGoogleAndBilling=True
                    ),
                    None,
                )
        self.assertEqual(error.exception.status_code, 403)
        authenticate.assert_not_called()
        client.assert_not_called()

if __name__ == "__main__":
    unittest.main()
