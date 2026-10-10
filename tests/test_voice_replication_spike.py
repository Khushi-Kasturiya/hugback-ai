import importlib.util
import sys
import tempfile
import unittest
import wave
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "check_live_voice_replication.py"
)
SPEC = importlib.util.spec_from_file_location("voice_replication_spike", SCRIPT_PATH)
assert SPEC and SPEC.loader
spike = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = spike
SPEC.loader.exec_module(spike)


def _write_wav(path: Path, rate: int = 24_000, channels: int = 1) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(b"\x00\x00" * rate * channels)


class VoiceReplicationSpikeTests(unittest.TestCase):
    def test_live_config_serializes_native_replication_audio(self):
        config = spike.build_replication_config(b"sample", b"consent")
        voice = config.speech_config.voice_config
        self.assertIsNotNone(voice.replicated_voice_config)
        self.assertEqual(
            voice.replicated_voice_config.voice_sample_audio,
            b"sample",
        )
        self.assertIsNone(voice.prebuilt_voice_config)

    def test_live_config_serializes_voice_identifier(self):
        config = spike.build_voice_id_config("voicekey_test")
        voice = config.speech_config.voice_config
        self.assertEqual(voice.voice, "voicekey_test")
        self.assertIsNone(voice.prebuilt_voice_config)
        self.assertIsNone(voice.replicated_voice_config)

    def test_wav_validator_accepts_required_format(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "valid.wav"
            _write_wav(path)
            recording = spike.load_voice_wav(path)
        self.assertEqual(recording.duration_seconds, 1.0)

    def test_wav_validator_rejects_wrong_sample_rate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.wav"
            _write_wav(path, rate=16_000)
            with self.assertRaisesRegex(ValueError, "must be 24 kHz"):
                spike.load_voice_wav(path)


if __name__ == "__main__":
    unittest.main()
