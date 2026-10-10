import base64
import io
import unittest
import wave

from app.agent.live_session import create_live_config
from app.voice.service import VoiceEnrollmentError, parse_inline_voice, validate_wav


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

    def test_rejects_partial_inline_voice_envelope(self):
        with self.assertRaisesRegex(VoiceEnrollmentError, "Both"):
            parse_inline_voice({"voiceSampleAudio": "abc"})


class LiveVoiceSelectionTests(unittest.TestCase):
    def test_managed_voice_id_replaces_prebuilt_voice(self):
        config = create_live_config(voice_id="voice_test123")
        voice = config.speech_config.voice_config
        self.assertEqual(voice.voice, "voice_test123")
        self.assertIsNone(voice.prebuilt_voice_config)

    def test_default_voice_remains_available(self):
        config = create_live_config()
        voice = config.speech_config.voice_config
        self.assertIsNotNone(voice.prebuilt_voice_config)
        self.assertIsNone(voice.voice)

    def test_inline_replication_replaces_prebuilt_voice(self):
        config = create_live_config(
            voice_sample_audio=b"sample",
            consent_audio=b"consent",
        )
        voice = config.speech_config.voice_config
        self.assertEqual(voice.replicated_voice_config.voice_sample_audio, b"sample")
        self.assertEqual(voice.replicated_voice_config.consent_audio, b"consent")
        self.assertIsNone(voice.prebuilt_voice_config)


if __name__ == "__main__":
    unittest.main()
