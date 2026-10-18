"""Synthetic, offline tests for the separate Voices API -> TTS probe."""

import asyncio
import base64
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch
import wave

import httpx


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_tts_voice_replication.py"
SPEC = importlib.util.spec_from_file_location("tts_voice_probe", SCRIPT)
probe = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = probe
SPEC.loader.exec_module(probe)


def wav_bytes(seconds=1):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24_000)
        wav.writeframes(b"\0\0" * 24_000 * seconds)
    return buffer.getvalue()


class TTSProbeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.sample, self.consent, self.output = (
            root / name for name in ("sample.wav", "consent.wav", "output.wav")
        )
        self.sample.write_bytes(wav_bytes(21))
        self.consent.write_bytes(wav_bytes())
        self.voice_key = "voicekey_synthetic-private"
        self.result = SimpleNamespace(
            status="completed",
            output_audio=SimpleNamespace(
                mime_type="audio/wav",
                data=base64.b64encode(wav_bytes()).decode("ascii"),
            ),
        )
        self.client = SimpleNamespace(
            aio=SimpleNamespace(
                voices=SimpleNamespace(create=AsyncMock(
                    return_value=SimpleNamespace(key=self.voice_key)
                )),
                interactions=SimpleNamespace(create=AsyncMock(return_value=self.result)),
                live=SimpleNamespace(connect=Mock()),
                aclose=AsyncMock(),
            ),
            close=Mock(),
        )

    def run_probe(self, **kwargs):
        return asyncio.run(probe.run_probe(
            self.sample, self.consent, self.output, **kwargs
        ))

    def test_dry_run_never_constructs_client_or_writes_output(self):
        with patch.object(probe.genai, "Client") as client, redirect_stdout(io.StringIO()):
            self.run_probe()
        client.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_cli_is_offline_by_default(self):
        args = probe.parse_args([
            "--sample", str(self.sample), "--consent", str(self.consent),
            "--output", str(self.output),
        ])
        self.assertFalse(args.run_live)
        self.assertFalse(args.confirm_consent_and_billing)

    def test_authorization_required_before_reading_or_uploading(self):
        with patch.object(probe, "load_wav") as load, self.assertRaisesRegex(
            probe.ProbeError, "confirm-consent-and-billing"
        ):
            self.run_probe(run_live=True)
        load.assert_not_called()

    def test_paid_key_route_enrolls_then_synthesizes_with_same_key_without_live(self):
        originals = self.sample.read_bytes(), self.consent.read_bytes()
        with (
            patch.object(probe.settings, "GEMINI_API_KEY", "synthetic-api-key"),
            patch.object(probe.genai, "Client", return_value=self.client) as create_client,
            redirect_stdout(io.StringIO()) as log,
        ):
            self.run_probe(run_live=True, confirm_consent_and_billing=True)
        config = create_client.call_args.kwargs
        self.assertFalse(config["vertexai"])
        self.assertEqual(config["api_key"], "synthetic-api-key")
        self.assertEqual(config["http_options"]["api_version"], "v1beta")
        self.assertEqual(config["http_options"]["retry_options"]["attempts"], 0)
        enrollment = self.client.aio.voices.create.call_args.kwargs
        self.assertFalse(enrollment["store"])
        self.assertEqual(enrollment["voice"]["type"], "replicated")
        self.assertEqual(
            base64.b64decode(enrollment["voice"]["replicated"]["source_audio"]["data"]),
            originals[0],
        )
        self.assertEqual(
            base64.b64decode(enrollment["voice"]["replicated"]["consent_audio"]["data"]),
            originals[1],
        )
        synthesis = self.client.aio.interactions.create.call_args.kwargs
        self.assertEqual(synthesis["model"], "gemini-3.8-flash-tts")
        self.assertFalse(synthesis["store"])
        self.assertEqual(
            synthesis["generation_config"]["speech_config"], [{"voice": self.voice_key}]
        )
        self.client.aio.voices.create.assert_awaited_once()
        self.client.aio.interactions.create.assert_awaited_once()
        self.client.aio.live.connect.assert_not_called()
        self.client.aio.aclose.assert_awaited_once()
        self.client.close.assert_called_once()
        self.assertEqual(self.output.read_bytes(), wav_bytes())
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.sample.read_bytes(), self.consent.read_bytes()), originals)
        self.assertNotIn(self.voice_key, log.getvalue())
        self.assertNotIn("synthetic-api-key", log.getvalue())
        self.assertIn("Not a cloning-success verdict", log.getvalue())

    def test_installed_sdk_preserves_both_http_payloads_without_network(self):
        requests = []

        def respond(request):
            body = json.loads(request.content)
            requests.append((request.url.path, body))
            if request.url.path == "/v1beta/voices":
                return httpx.Response(200, json={"key": self.voice_key, "type": "replicated"})
            self.assertEqual(request.url.path, "/v1beta/interactions")
            return httpx.Response(200, json={
                "status": "completed",
                "steps": [{
                    "type": "model_output",
                    "content": [{
                        "type": "audio", "mime_type": "audio/wav",
                        "data": self.result.output_audio.data,
                    }],
                }],
            })

        client = probe.create_tts_client(
            "offline-placeholder", transport=httpx.MockTransport(respond),
        )
        with (
            patch.object(probe.settings, "GEMINI_API_KEY", "offline-placeholder"),
            patch.object(probe.genai, "Client", return_value=client),
            redirect_stdout(io.StringIO()) as log,
        ):
            self.run_probe(run_live=True, confirm_consent_and_billing=True)
        self.assertEqual([path for path, _ in requests], [
            "/v1beta/voices", "/v1beta/interactions",
        ])
        enrollment, synthesis = [body for _, body in requests]
        self.assertFalse(enrollment["store"])
        self.assertFalse(synthesis["store"])
        self.assertEqual(enrollment["voice"]["type"], "replicated")
        self.assertEqual(
            base64.b64decode(enrollment["voice"]["replicated"]["source_audio"]["data"]),
            self.sample.read_bytes(),
        )
        self.assertEqual(
            base64.b64decode(enrollment["voice"]["replicated"]["consent_audio"]["data"]),
            self.consent.read_bytes(),
        )
        self.assertEqual(
            synthesis["generation_config"]["speech_config"], [{"voice": self.voice_key}]
        )
        self.assertEqual(self.output.read_bytes(), wav_bytes())
        self.assertNotIn(self.voice_key, log.getvalue())

    def test_installed_sdk_does_not_retry_a_provider_failure(self):
        paths = []

        def respond(request):
            paths.append(request.url.path)
            return httpx.Response(503, json={
                "error": {"code": 503, "status": "UNAVAILABLE", "message": "Synthetic fault"}
            })

        client = probe.create_tts_client(
            "offline-placeholder", transport=httpx.MockTransport(respond),
        )
        with (
            patch.object(probe.settings, "GEMINI_API_KEY", "offline-placeholder"),
            patch.object(probe.genai, "Client", return_value=client),
            redirect_stdout(io.StringIO()),
            self.assertRaises(Exception) as error,
        ):
            self.run_probe(run_live=True, confirm_consent_and_billing=True)
        self.assertEqual(paths, ["/v1beta/voices"])
        self.assertFalse(self.output.exists())
        self.assertIn("repeated API transmission was blocked", probe.safe_error_message(error.exception))

    def test_sdk_403_reports_provider_reason_without_request_or_metadata(self):
        def respond(request):
            return httpx.Response(403, json={
                "error": {
                    "code": 403,
                    "status": "PERMISSION_DENIED",
                    "message": "Voice replication requires explicit project access.",
                    "details": [{"metadata": {"private": "do-not-print-this"}}],
                },
            })

        client = probe.create_tts_client(
            "offline-placeholder", transport=httpx.MockTransport(respond),
        )
        with (
            patch.object(probe.settings, "GEMINI_API_KEY", "offline-placeholder"),
            patch.object(probe.genai, "Client", return_value=client),
            redirect_stdout(io.StringIO()),
            self.assertRaises(Exception) as error,
        ):
            self.run_probe(run_live=True, confirm_consent_and_billing=True)
        message = probe.safe_error_message(error.exception)
        self.assertIn("HTTP 403", message)
        self.assertIn("Google: Voice replication requires explicit project access.", message)
        self.assertNotIn("do-not-print-this", message)
        self.assertNotIn("offline-placeholder", message)
        self.assertNotIn(base64.b64encode(self.sample.read_bytes()).decode(), message)
        self.assertFalse(self.output.exists())

    def test_provider_message_redacts_sensitive_values_and_bounds_output(self):
        api_key = "AIza" + "X" * 35
        encoded_audio = "A" * 200
        private_text = "synthetic private sentence"
        message = (
            "Request denied. "
            f"{api_key} voicekey_private Bearer opaque-token "
            "https://example.invalid/?key=another-secret person@example.invalid "
            f"/Users/example/private.wav {encoded_audio} \"{private_text}\" "
        )
        with patch.object(probe.settings, "GEMINI_API_KEY", api_key):
            redacted = probe.redact_provider_message(message)
        for private in (
            api_key, "voicekey_private", "opaque-token", "another-secret",
            "person@example.invalid", "/Users/example/private.wav", encoded_audio,
            private_text,
        ):
            self.assertNotIn(private, redacted)
        self.assertIn("Request denied.", redacted)
        self.assertLessEqual(len(probe.redact_provider_message("test " * 200)), 500)

    def test_legacy_sdk_details_and_missing_provider_reason_are_supported(self):
        from google.genai.errors import ClientError

        error = ClientError(403, {"error": {
            "message": "Requests from this IP address are blocked.",
        }})
        self.assertIn(
            "Google: Requests from this IP address are blocked.",
            probe.safe_error_message(error),
        )
        error = ClientError(403, {"error": {"metadata": {"private": "not-a-message"}}})
        self.assertIn("No structured provider reason", probe.safe_error_message(error))
        self.assertNotIn("not-a-message", probe.safe_error_message(error))

    def test_missing_voice_key_never_falls_back_to_preset_or_synthesizes(self):
        self.client.aio.voices.create.return_value = SimpleNamespace(key=None, id="voice_other")
        with (
            patch.object(probe.settings, "GEMINI_API_KEY", "synthetic-api-key"),
            patch.object(probe.genai, "Client", return_value=self.client),
            redirect_stdout(io.StringIO()),
            self.assertRaisesRegex(probe.ProbeError, "No client-managed"),
        ):
            self.run_probe(run_live=True, confirm_consent_and_billing=True)
        self.client.aio.interactions.create.assert_not_awaited()
        self.client.aio.aclose.assert_awaited_once()
        self.assertFalse(self.output.exists())

    def test_provider_error_stops_without_retry_synthesis_or_private_error_logging(self):
        self.client.aio.voices.create.side_effect = RuntimeError("private-audio-data")
        with (
            patch.object(probe.settings, "GEMINI_API_KEY", "synthetic-api-key"),
            patch.object(probe.genai, "Client", return_value=self.client),
            redirect_stdout(io.StringIO()),
            self.assertRaises(RuntimeError) as error,
        ):
            self.run_probe(run_live=True, confirm_consent_and_billing=True)
        self.client.aio.voices.create.assert_awaited_once()
        self.client.aio.interactions.create.assert_not_awaited()
        self.client.aio.aclose.assert_awaited_once()
        self.assertNotIn("private-audio-data", probe.safe_error_message(error.exception))
        self.assertFalse(self.output.exists())

    def test_existing_file_and_racing_file_are_never_overwritten(self):
        self.output.write_bytes(b"previous result")
        with self.assertRaisesRegex(probe.ProbeError, "already exists"):
            self.run_probe()
        with self.assertRaises(FileExistsError):
            probe.save_new_output(self.output, wav_bytes())
        self.assertEqual(self.output.read_bytes(), b"previous result")

    def test_inputs_cannot_be_replaced(self):
        with self.assertRaisesRegex(probe.ProbeError, "replace an input"):
            asyncio.run(probe.run_probe(self.sample, self.consent, self.sample))

    def test_missing_api_key_has_no_adc_fallback(self):
        with (
            patch.object(probe.settings, "GEMINI_API_KEY", None),
            patch.object(probe.genai, "Client") as client,
            redirect_stdout(io.StringIO()),
            self.assertRaisesRegex(probe.ProbeError, "no Vertex/ADC"),
        ):
            self.run_probe(run_live=True, confirm_consent_and_billing=True)
        client.assert_not_called()

    def test_output_validation_rejects_incomplete_or_mislabelled_audio(self):
        for status, mime, data in (
            ("in_progress", "audio/wav", self.result.output_audio.data),
            ("completed", "audio/mpeg", self.result.output_audio.data),
            ("completed", "audio/wav", "not-base64!"),
            ("completed", "audio/wav", base64.b64encode(b"not a wav").decode()),
            ("completed", "audio/wav", None),
        ):
            with self.subTest(status=status, mime=mime), self.assertRaises(ValueError):
                probe.decode_output(SimpleNamespace(
                    status=status, output_audio=SimpleNamespace(mime_type=mime, data=data)
                ))

    def test_live_models_and_long_prompts_are_rejected_before_client_creation(self):
        for kwargs in ({"model": "gemini-3.8-live"}, {"text": "x" * 281}, {"text": " "}):
            with patch.object(probe.genai, "Client") as client, self.assertRaises(ValueError):
                self.run_probe(**kwargs)
            client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
