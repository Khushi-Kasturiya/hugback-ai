"""Content-free diagnostics for failed Gemini Live sessions."""

import unittest

from google.genai.errors import APIError

from app.main import live_failure_detail


class LiveFailureMessageTests(unittest.TestCase):
    def test_provider_status_is_actionable_without_echoing_private_body(self):
        for code, expected in ((400, "settings"), (403, "project"),
                               (404, "model"), (429, "quota"), (503, "unavailable")):
            with self.subTest(code=code):
                error = APIError(code, {"error": {"message": "private voice data and API key"}})
                actual_code, detail = live_failure_detail(error, connected=False)
                self.assertEqual(actual_code, code)
                self.assertIn(f"HTTP {code}", detail)
                self.assertIn(expected, detail)
                self.assertNotIn("private", detail)
                self.assertNotIn("API key", detail.split("HTTP ")[0])

    def test_connected_failure_is_not_called_initial_setup(self):
        error = APIError(503, {"error": {"message": "private"}})
        _, detail = live_failure_detail(error, connected=True)
        self.assertIn("connection stopped", detail)
        self.assertNotIn("did not open", detail)

    def test_websocket_close_code_is_not_misreported_as_http(self):
        for code, expected in ((1011, "Google AI Studio"), (1006, "network or VPN")):
            with self.subTest(code=code):
                error = APIError(code, "private provider close reason with sample")
                actual_code, detail = live_failure_detail(error, connected=False)
                self.assertEqual(actual_code, code)
                self.assertIn(f"WebSocket {code}", detail)
                self.assertIn(expected, detail)
                self.assertNotIn("HTTP", detail)
                self.assertNotIn("private", detail)

    def test_unknown_error_does_not_expose_exception_text(self):
        code, detail = live_failure_detail(RuntimeError("private audio and credentials"), connected=False)
        self.assertIsNone(code)
        self.assertNotIn("private", detail)
        self.assertNotIn("credentials", detail)


if __name__ == "__main__":
    unittest.main()
