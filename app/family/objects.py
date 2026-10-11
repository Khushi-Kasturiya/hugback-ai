"""Private, immutable original files. No signed/public URLs, tokens, TTL or delete API."""
import hashlib

from app.config import settings
from app.family.models import MAX_FILE_BYTES
from app.family.parser import FamilyError


class PrivateObjects:
    def __init__(self):
        from google.cloud import storage
        self.client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT)
        self.bucket = self.client.bucket(settings.CLOUD_IMPORT_BUCKET)
        self.checked = False

    def check_private(self):
        if self.checked:
            return
        self.bucket.reload(timeout=10, retry=None)
        iam = self.bucket.iam_configuration
        if not iam.uniform_bucket_level_access_enabled or iam.public_access_prevention != "enforced":
            raise FamilyError("The import bucket must enforce public access prevention and uniform bucket-level access.", 503)
        if any(rule.get("action", {}).get("type") == "Delete" for rule in self.bucket.lifecycle_rules):
            raise FamilyError("Use an import bucket without automatic lifecycle deletion. Originals must be retained.", 503)
        self.checked = True

    def put(self, path, raw, sha):
        from google.api_core.exceptions import PreconditionFailed
        if not 0 < len(raw) <= MAX_FILE_BYTES or hashlib.sha256(raw).hexdigest() != sha:
            raise FamilyError("Original file integrity could not be confirmed.", 409)
        self.check_private()
        blob = self.bucket.blob(path)
        blob.metadata = {"elaraSha256": sha}
        # No filename-based path, no overwrite, no automatic upload retry.
        try:
            blob.upload_from_string(raw, content_type="application/octet-stream",
                                    if_generation_match=0, timeout=30, retry=None)
        except PreconditionFailed:
            # A prior attempt may have saved bytes before its Firestore commit failed.
            blob.reload(timeout=10, retry=None)
            if blob.size != len(raw) or (blob.metadata or {}).get("elaraSha256") != sha:
                raise FamilyError("An existing original did not match this import. Nothing was overwritten.", 409)
            # Do not trust matching custom metadata alone. Confirm the bytes of
            # the exact generation before recovering a partially completed save.
            self.get(path, str(blob.generation), sha, len(raw))
        if not blob.generation:
            raise FamilyError("Storage did not confirm an original generation.", 503)
        return str(blob.generation)

    def get(self, path, generation, sha, size):
        self.check_private()
        blob = self.bucket.blob(path, generation=int(generation))
        blob.reload(timeout=10, retry=None)
        if not 0 < size <= MAX_FILE_BYTES or blob.size != size:
            raise FamilyError("Original file integrity could not be confirmed.", 409)
        raw = blob.download_as_bytes(if_generation_match=int(generation), raw_download=True, timeout=30, retry=None)
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != sha:
            raise FamilyError("Original file integrity could not be confirmed.", 409)
        return raw

    def close(self):
        self.client.close()
