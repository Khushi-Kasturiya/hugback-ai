import asyncio
import base64
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import wave
from contextlib import asynccontextmanager, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from google import genai
from google.genai import types


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


def _write_wav(
    path: Path, rate: int = 24_000, channels: int = 1, seconds: int = 1
) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(b"\x00\x00" * rate * channels * seconds)


class VoiceReplicationSpikeTests(unittest.TestCase):
    def test_actual_sdk_websocket_setup_preserves_replication_fields_offline(self):
        """Exercise real SDK serialization, not only Pydantic construction."""
        sent = []
        sample, consent = b"synthetic reference", b"synthetic consent"

        class FakeSocket:
            async def send(self, data):
                sent.append(json.loads(data))

            async def recv(self, **kwargs):
                return b'{"setupComplete": {}}'

        @asynccontextmanager
        async def connect(*args, **kwargs):
            yield FakeSocket()

        async def run():
            client = genai.Client(
                api_key="offline-test-key",
                vertexai=False,
                http_options={"api_version": "v1alpha"},
            )
            try:
                with patch("google.genai.live.ws_connect", connect):
                    async with client.aio.live.connect(
                        model="gemini-3.8-live",
                        config=spike.build_replication_config(sample, consent),
                    ):
                        pass
            finally:
                await client.aio.aclose()
                client.close()

        asyncio.run(run())
        self.assertEqual(len(sent), 1)
        speech = sent[0]["setup"]["generationConfig"]["speechConfig"]
        voice = speech.get("voice_config", speech.get("voiceConfig", {}))
        replicated = voice.get(
            "replicated_voice_config", voice.get("replicatedVoiceConfig", {})
        )
        self.assertEqual(
            base64.urlsafe_b64decode(replicated.get(
                "voice_sample_audio", replicated.get("voiceSampleAudio", "")
            )),
            sample,
        )
        self.assertEqual(
            base64.urlsafe_b64decode(replicated.get(
                "consent_audio", replicated.get("consentAudio", "")
            )),
            consent,
        )
        self.assertNotIn("prebuilt_voice_config", voice)
        self.assertNotIn("prebuiltVoiceConfig", voice)

    def test_consent_gate_rejects_missing_or_empty_server_evidence(self):
        for setup in (
            None,
            types.LiveServerSetupComplete(),
            types.LiveServerSetupComplete(
                voice_consent_signature=types.VoiceConsentSignature()
            ),
            types.LiveServerSetupComplete(
                voice_consent_signature=types.VoiceConsentSignature(signature=" ")
            ),
        ):
            with self.subTest(setup=setup), self.assertRaisesRegex(
                RuntimeError, "NOT verified"
            ):
                spike.require_live_consent_acknowledgement(setup)

    def test_sdk_probe_stops_before_speech_when_consent_evidence_is_missing(self):
        session = SimpleNamespace(
            setup_complete=types.LiveServerSetupComplete(),
            send_client_content=AsyncMock(),
        )

        @asynccontextmanager
        async def connect(**kwargs):
            yield session

        client = SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sample, consent, output = root / "sample.wav", root / "consent.wav", root / "out.wav"
            _write_wav(sample, seconds=10)
            _write_wav(consent)
            with (
                patch.object(spike, "create_genai_client", return_value=client),
                redirect_stdout(io.StringIO()),
                self.assertRaisesRegex(RuntimeError, "NOT verified"),
            ):
                asyncio.run(spike.run_spike(
                    sample, consent, output, "Synthetic test.", "inline",
                    run_live=True, confirm_consent=True, wire_format="sdk-wav",
                ))
            session.send_client_content.assert_not_awaited()
            self.assertFalse(output.exists())

    def test_acknowledged_consent_allows_audio_but_not_a_cloning_verdict(self):
        signature = "synthetic-private-signature"
        response = SimpleNamespace(server_content=SimpleNamespace(
            model_turn=SimpleNamespace(parts=[
                SimpleNamespace(inline_data=SimpleNamespace(data=b"\0\0" * 2400))
            ]),
            output_transcription=None,
            turn_complete=True,
        ))

        class FakeSession:
            setup_complete = types.LiveServerSetupComplete(
                voice_consent_signature=types.VoiceConsentSignature(signature=signature)
            )
            send_client_content = AsyncMock()

            async def receive(self):
                yield response

        session = FakeSession()

        @asynccontextmanager
        async def connect(**kwargs):
            yield session

        client = SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=connect)))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sample, consent, output = root / "sample.wav", root / "consent.wav", root / "out.wav"
            _write_wav(sample, seconds=10)
            _write_wav(consent)
            with (
                patch.object(spike, "create_genai_client", return_value=client),
                redirect_stdout(io.StringIO()) as log,
            ):
                asyncio.run(spike.run_spike(
                    sample, consent, output, "Synthetic test.", "inline",
                    run_live=True, confirm_consent=True, wire_format="sdk-wav",
                ))
            session.send_client_content.assert_awaited_once()
            self.assertTrue(output.exists())
            self.assertIn("AUDIO RECEIVED ONLY", log.getvalue())
            self.assertIn("likeness is still unverified", log.getvalue())
            self.assertNotIn(signature, log.getvalue())

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

    def test_reference_selection_preserves_original_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.wav"
            _write_wav(path, seconds=27)
            original_bytes = path.read_bytes()
            original = spike.load_voice_wav(path, minimum_seconds=10)
            selected = spike.prepare_reference(original, 20)
            self.assertEqual(selected.duration_seconds, 20)
            self.assertEqual(original.duration_seconds, 27)
            self.assertEqual(path.read_bytes(), original_bytes)
            with wave.open(io.BytesIO(selected.data), "rb") as recording:
                self.assertEqual(recording.getnframes(), 20 * 24_000)

    def test_reference_selection_rejects_out_of_bounds_duration(self):
        recording = spike.WavRecording(data=b"unused", duration_seconds=10)
        for seconds in (9, 11, 21):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                spike.prepare_reference(recording, seconds)

    def test_cloud_pcm_payload_has_no_wav_header_and_no_consent_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.wav"
            _write_wav(path, seconds=10)
            config = spike.build_replication_config(
                path.read_bytes(), b"not transmitted", wire_format="cloud-pcm"
            )
        replicated = config.speech_config.voice_config.replicated_voice_config
        self.assertEqual(replicated.mime_type, "audio/pcm;rate=24000")
        self.assertEqual(len(replicated.voice_sample_audio), 10 * 24_000 * 2)
        self.assertFalse(replicated.voice_sample_audio.startswith(b"RIFF"))
        self.assertIsNone(replicated.consent_audio)

    def test_cloud_pcm_rejects_long_reference_instead_of_silent_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.wav"
            _write_wav(path, seconds=27)
            with self.assertRaisesRegex(ValueError, "10–20"):
                spike.build_replication_config(
                    path.read_bytes(), b"consent", wire_format="cloud-pcm"
                )

    def test_cli_is_offline_by_default(self):
        args = spike.parse_args(["--sample", "/sample.wav", "--consent", "/consent.wav"])
        self.assertFalse(args.run_live)
        self.assertFalse(args.confirm_consent)
        self.assertIsNone(args.wire_format)
        self.assertIsNone(args.reference_seconds)

    def test_dry_run_does_not_create_clients_profiles_or_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sample, consent, output = root / "sample.wav", root / "consent.wav", root / "new.wav"
            _write_wav(sample, seconds=27)
            _write_wav(consent, seconds=2)
            with (
                patch.object(spike, "create_genai_client") as client,
                patch.object(spike, "create_ephemeral_voice_key") as enroll,
                patch("google.genai.Client") as cloud_client,
                redirect_stdout(io.StringIO()) as log,
            ):
                for mode, wire_format in (("inline", "cloud-pcm"), ("voice-key", None)):
                    asyncio.run(
                        spike.run_spike(
                            sample, consent, output, "Synthetic test.", mode,
                            reference_seconds=20, wire_format=wire_format,
                        )
                    )
                client.assert_not_called()
                cloud_client.assert_not_called()
                enroll.assert_not_called()
                self.assertIn("DRY RUN", log.getvalue())
            self.assertFalse(output.exists())

    def test_live_probe_requires_consent_before_reading_files(self):
        with (
            patch.object(spike, "load_voice_wav") as load,
            patch.object(spike, "create_genai_client") as client,
            self.assertRaisesRegex(ValueError, "confirm-consent"),
        ):
            asyncio.run(
                spike.run_spike(
                    Path("/sample"), Path("/consent"), Path("/output"),
                    "Synthetic test.", "inline", run_live=True, wire_format="sdk-wav",
                )
            )
        load.assert_not_called()
        client.assert_not_called()

    def test_live_inline_probe_requires_explicit_wire_format(self):
        with (
            patch.object(spike, "load_voice_wav") as load,
            self.assertRaisesRegex(ValueError, "wire-format"),
        ):
            asyncio.run(
                spike.run_spike(
                    Path("/sample"), Path("/consent"), Path("/output"),
                    "Synthetic test.", "inline", run_live=True, confirm_consent=True,
                )
            )
        load.assert_not_called()

    def test_output_must_not_replace_inputs_or_existing_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sample, consent, previous = root / "sample.wav", root / "consent.wav", root / "old.wav"
            for path in (sample, consent, previous):
                path.write_bytes(b"synthetic original")
            for output in (sample, consent, previous):
                with self.subTest(output=output.name), self.assertRaises(ValueError):
                    asyncio.run(
                        spike.run_spike(sample, consent, output, "Test.", "inline")
                    )
                self.assertEqual(output.read_bytes(), b"synthetic original")

    def test_loader_rejects_missing_truncated_and_oversized_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.wav"
            with self.assertRaisesRegex(ValueError, "could not be read"):
                spike.load_voice_wav(path)
            _write_wav(path)
            path.write_bytes(path.read_bytes()[:-2])
            with self.assertRaisesRegex(ValueError, "truncated"):
                spike.load_voice_wav(path)
            path.write_bytes(b"\0" * (spike.MAX_WAV_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "size limit"):
                spike.load_voice_wav(path)

    def test_authorized_cloud_path_uses_cloud_client_and_writes_new_output(self):
        captured_configs = []
        response = SimpleNamespace(
            server_content=SimpleNamespace(
                model_turn=SimpleNamespace(parts=[
                    SimpleNamespace(inline_data=SimpleNamespace(data=b"\0\0" * 2400))
                ]),
                output_transcription=SimpleNamespace(text="Synthetic private response"),
                turn_complete=True,
            )
        )

        class FakeSession:
            send_client_content = AsyncMock()

            async def receive(self):
                yield response

        @asynccontextmanager
        async def connect(*, model, config):
            captured_configs.append(config)
            yield FakeSession()

        fake_client = SimpleNamespace(
            aio=SimpleNamespace(live=SimpleNamespace(connect=connect))
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sample, consent, output = root / "sample.wav", root / "consent.wav", root / "new.wav"
            _write_wav(sample, seconds=27)
            _write_wav(consent, seconds=2)
            with (
                patch("google.genai.Client", return_value=fake_client) as cloud_client,
                patch.object(spike, "create_genai_client") as default_client,
                redirect_stdout(io.StringIO()) as log,
            ):
                asyncio.run(
                    spike.run_spike(
                        sample, consent, output, "Synthetic test.", "inline",
                        run_live=True, confirm_consent=True,
                        reference_seconds=20, wire_format="cloud-pcm",
                    )
                )
                self.assertTrue(cloud_client.call_args.kwargs["vertexai"])
                self.assertNotIn("api_key", cloud_client.call_args.kwargs)
                default_client.assert_not_called()
                self.assertNotIn("Synthetic private response", log.getvalue())
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            with wave.open(str(output), "rb") as audio:
                self.assertEqual(audio.getnframes(), 2400)
                self.assertEqual(audio.getframerate(), 24_000)
            replicated = captured_configs[0].speech_config.voice_config.replicated_voice_config
            self.assertEqual(len(replicated.voice_sample_audio), 20 * 24_000 * 2)
            self.assertIsNone(replicated.consent_audio)


if __name__ == "__main__":
    unittest.main()
