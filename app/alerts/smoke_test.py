"""Operator-only fictional SMTP readiness check and explicit probe.

Run from the backend repository: python -m app.alerts.smoke_test [--send --to ADDRESS]
No address, password, or provider exception is printed.
"""

import argparse

from app.alerts.email import configured, send_test_probe, valid_destination
from app.config import settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the fictional Gmail SMTP notice setup")
    parser.add_argument("--send", action="store_true", help="send one generic test email")
    parser.add_argument("--to", help="destination for --send; use an inbox that expects the fictional test")
    args = parser.parse_args()

    checks = {
        "LOCAL_DEMO_ENABLED": settings.LOCAL_DEMO_ENABLED,
        "HUGBACK_ALERT_EMAIL_ENABLED": settings.HUGBACK_ALERT_EMAIL_ENABLED,
        "HUGBACK_ALERT_SMTP_USERNAME": bool(settings.HUGBACK_ALERT_SMTP_USERNAME),
        "HUGBACK_ALERT_SMTP_APP_PASSWORD": bool(settings.HUGBACK_ALERT_SMTP_APP_PASSWORD),
        "Gmail sender ready": configured(),
    }
    for name, ready in checks.items():
        print(f"{name}: {'ready' if ready else 'missing or off'}")
    if not all(checks.values()):
        print("No email sent. Complete the private backend .env setup, then rerun.")
        return 2
    if not args.send:
        print("Ready. No email sent; use --send --to ADDRESS for one fictional probe.")
        return 0
    if not args.to or not valid_destination(args.to):
        print("No email sent. --send requires a valid --to test inbox.")
        return 2
    try:
        send_test_probe(args.to)
    except Exception as exc:
        print(f"SMTP probe failed ({type(exc).__name__}). Check Gmail credentials, network, and test inbox.")
        return 1
    print("SMTP accepted the fictional probe. Check the test inbox and spam folder for delivery.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
