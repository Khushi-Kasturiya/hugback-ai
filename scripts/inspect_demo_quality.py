"""Trusted operator-only, content-free quality reports. Never a browser endpoint."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.demo.service import get_demo_store

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True, help="Development ID, or firebase:UID for an allowlisted cloud test owner")
    parser.add_argument("--recipient", required=True)
    parser.add_argument("--allow-cloud-read", action="store_true")
    args = parser.parse_args()
    if settings.HUGBACK_DEMO_STORE == "firestore" and not args.allow_cloud_read:
        parser.error("Firestore inspection requires --allow-cloud-read")
    settings.validate_test_mode()
    print(json.dumps(get_demo_store().inspect_quality(args.owner, args.recipient), indent=2))

if __name__ == "__main__": main()
