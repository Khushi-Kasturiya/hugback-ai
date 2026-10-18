"""Optional Gmail SMTP sender for bounded fictional-call notifications."""

from email.message import EmailMessage
import re
import smtplib
import ssl

import certifi

from app.config import settings

_EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?$", re.ASCII)


def configured() -> bool:
    base = bool(
        settings.LOCAL_DEMO_ENABLED
        and settings.HUGBACK_ALERT_EMAIL_ENABLED
        and settings.HUGBACK_ALERT_SMTP_USERNAME
        and settings.HUGBACK_ALERT_SMTP_APP_PASSWORD
        and _EMAIL.fullmatch(settings.HUGBACK_ALERT_SMTP_USERNAME)
    )
    if not base:
        return False
    return bool(settings.HUGBACK_DEMO_STORE == "sqlite" or (
        settings.HUGBACK_DEMO_STORE == "firestore"
        and settings.HUGBACK_CLOUD_TEST_ENABLED
        and settings.HUGBACK_AUTH_MODE == "firebase"
    ))


def valid_destination(address: str) -> bool:
    return bool(address and _EMAIL.fullmatch(address))


def send_test_notice(recipient_label: str, call_time: str, destination: str,
                     child_name: str | None = None) -> None:
    """Send no excerpt, topic, medical claim, or transcript outside the portal."""
    if not configured() or not valid_destination(destination):
        raise RuntimeError("Synthetic alert email is not configured")
    message = EmailMessage()
    message["From"] = settings.HUGBACK_ALERT_SMTP_USERNAME
    message["To"] = destination
    message["Subject"] = "HugBack call update"
    greeting = f"Hello {child_name},\n\n" if child_name else ""
    message.set_content(
        greeting + "A topic you chose to be notified about came up in a fictional HugBack "
        f"call with {recipient_label} at {call_time}.\n\n"
        f"Open HugBack: {settings.HUGBACK_PORTAL_URL}\n\n"
        "This automatic notice may be inaccurate or delayed. It is not an emergency alert."
    )
    _send(message)


def send_call_summary(recipient_label: str, call_time: str, destination: str,
                      summary: str, child_name: str | None = None) -> None:
    """Email exactly the already-bounded stored summary, never raw call turns."""
    if (not configured() or not valid_destination(destination)
            or not isinstance(summary, str) or not 20 <= len(summary) <= 600):
        raise RuntimeError("Synthetic summary email is not configured")
    message = EmailMessage()
    message["From"] = settings.HUGBACK_ALERT_SMTP_USERNAME
    message["To"] = destination
    message["Subject"] = f"HugBack call summary · {recipient_label}"
    greeting = f"Hello {child_name},\n\n" if child_name else "Hello,\n\n"
    message.set_content(
        greeting + f"Here is the short summary of the HugBack call with {recipient_label} "
        f"at {call_time}:\n\n{summary}\n\n"
        f"Open HugBack: {settings.HUGBACK_PORTAL_URL}\n\n"
        "This AI-generated summary may miss details or reflect speech-recognition errors."
    )
    _send(message)


def send_test_probe(destination: str) -> None:
    """Explicit operator smoke test; does not create a call or topic event."""
    if not configured() or not valid_destination(destination):
        raise RuntimeError("Synthetic alert email is not configured")
    message = EmailMessage()
    message["From"] = settings.HUGBACK_ALERT_SMTP_USERNAME
    message["To"] = destination
    message["Subject"] = "HugBack fictional email test"
    message.set_content(
        "This is an operator-requested test of the fictional HugBack email sender. "
        "It was not triggered by a call.\n\n"
        f"Open HugBack: {settings.HUGBACK_PORTAL_URL}\n\n"
        "This is not an emergency alert."
    )
    _send(message)


def _send(message: EmailMessage) -> None:
    """Keep probe and call notices on the same TLS/authentication path."""
    if not configured():
        raise RuntimeError("Synthetic alert email is not configured")
    # Google displays app passwords in grouped blocks. SMTP expects the compact
    # value, so tolerate copied display whitespace without logging the secret.
    app_password = "".join(settings.HUGBACK_ALERT_SMTP_APP_PASSWORD.split())
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=8) as client:
        client.ehlo()
        # This Python build has no default CA certificates on macOS. Keep TLS
        # verification enabled with a maintained CA bundle.
        client.starttls(context=ssl.create_default_context(cafile=certifi.where()))
        client.ehlo()
        client.login(settings.HUGBACK_ALERT_SMTP_USERNAME, app_password)
        client.send_message(message)
