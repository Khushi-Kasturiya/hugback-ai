"""Operator-run no-app intake sink. Offline validation is the default.

No Drive watcher, cloud provisioning, consent grant, or model/call activation.
The operator supplies a private export already obtained through authorized
Forms/Drive intake and a trusted recipient mapping. Never accept this manifest
directly from an untrusted Form respondent.
"""
import argparse
import base64
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError

from app.family.models import ImportInput, IntakeManifest, MAX_FILE_BYTES
from app.family.parser import FamilyError, decode_upload
from app.family.service import digest, service


def read_bounded(path: Path, limit: int) -> bytes:
    with path.open("rb") as source:
        raw = source.read(limit + 1)
    if len(raw) > limit:
        raise FamilyError("Input exceeds the allowed size.")
    return raw


def prepare(manifest_path: Path, original_path: Path):
    manifest = IntakeManifest.model_validate_json(read_bounded(manifest_path, 16_384))
    raw = read_bounded(original_path, MAX_FILE_BYTES)
    request = ImportInput(filename=original_path.name, fileBase64=base64.b64encode(raw).decode("ascii"),
                          **manifest.mapping.model_dump())
    _, messages = decode_upload(request)
    return manifest, request, {"bytes": len(raw), "messages": len(messages)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="Private operator-owned setup JSON; not a raw Form response.")
    parser.add_argument("--file", type=Path, required=True, help="Authorized UTF-8 WhatsApp .txt export; read-only.")
    parser.add_argument("--execute", action="store_true", help="Explicitly write to existing Google resources; defaults to offline validation.")
    parser.add_argument("--acknowledge-cloud-storage", action="store_true", help="Acknowledge authorized Google storage, retention and possible charges.")
    args = parser.parse_args(argv)
    if args.execute and not args.acknowledge_cloud_storage:
        parser.error("--execute requires --acknowledge-cloud-storage")
    try:
        manifest, request, counts = prepare(args.manifest, args.file)
        if not args.execute:
            print(json.dumps({"mode": "offline_validation", **counts, "cloudAccessed": False,
                              "contextActive": False}))
            return 0
        with service() as backend:
            # Stable operator-assigned IDs make uncertain retries idempotent.
            backend.create_family(manifest.ownerId)
            backend.add_recipient(manifest.ownerId, manifest.recipient)
            rid = "recipient-" + digest([manifest.ownerId, manifest.recipient.requestId])[:32]
            saved = backend.upload(manifest.ownerId, rid, request)
        # No phone, names, filenames, message text, object URLs or auth data.
        print(json.dumps({"mode": "stored", "recipientId": rid, "importId": saved["importId"],
                          "originalRetained": saved["originalRetained"], "contextActive": False}))
        return 0
    except (OSError, ValueError, ValidationError):
        print("Intake could not be confirmed. Check the private inputs and configuration; "
              "no local fallback or call activation was used. If execution was requested, "
              "retry only with the same unchanged IDs, mapping and original file.", file=sys.stderr)
        return 1
    except Exception:
        # Provider messages can include private paths, content or identifiers.
        print("Google intake could not confirm completion. Data may be pending. "
              "Retry the same unchanged submission after checking service access. "
              "No call context was activated.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
