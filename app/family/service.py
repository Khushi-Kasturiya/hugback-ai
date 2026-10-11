"""Cloud intake state machine. Upload retention and call-context permission are separate."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import re

from app.config import settings
from app.family.models import MAX_IMPORTS, MAX_RECIPIENTS
from app.family.parser import FamilyError, PARSER_VERSION, decode_upload, parse


def now():
    return datetime.now(timezone.utc)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def configured():
    return bool(settings.CLOUD_INTAKE_ENABLED and settings.FIRESTORE_ENABLED
                and settings.GOOGLE_CLOUD_PROJECT and settings.FIRESTORE_DATABASE
                and re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,61}[a-z0-9]", settings.CLOUD_IMPORT_BUCKET))


def family_id(uid):
    return "family-" + hashlib.sha256(("elara-cloud-family:" + uid).encode()).hexdigest()


def valid_id(value, kind):
    pattern = r"recipient-[a-f0-9]{32}" if kind == "recipient" else r"[a-f0-9]{64}"
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise FamilyError("Invalid recipient or import identifier.", 404)
    return value


def owner_check(family, uid):
    if not family or family.get("ownerId") != uid:
        raise FamilyError("This cloud family is not available to this identity.", 404)


def public_recipient(recipient):
    return {key: recipient[key] for key in ("recipientId", "label", "relationship", "phone", "language", "timeZone", "createdAt")}


class FamilyService:
    """Trusted internal worker API, not an end-user authentication boundary.

    The caller must resolve stable owner/recipient identities from a trusted
    intake registry. A Form field or phone number is not proof of that mapping.
    No method here activates context, grants consent, or contacts a model.
    """
    def __init__(self, repository, objects):
        self.repo, self.objects = repository, objects

    def paths(self, uid, rid=None, iid=None):
        root = "cloud_families/" + family_id(uid)
        recipient = root + "/recipients/" + valid_id(rid, "recipient") if rid else None
        imported = recipient + "/imports/" + valid_id(iid, "import") if iid and recipient else None
        return root, recipient, imported

    def create_family(self, uid):
        root, _, _ = self.paths(uid)
        def create(state):
            if state[root]:
                owner_check(state[root], uid)
                return {}, None
            return {root: {"familyId": family_id(uid), "ownerId": uid, "createdAt": now(),
                           "recipientLabels": [], "schemaVersion": 1}}, None
        self.repo.transact([root], create)
        return self.get_family(uid)

    def get_family(self, uid):
        root, _, _ = self.paths(uid)
        data = self.repo.read(root)
        owner_check(data, uid)
        recipients = self.repo.list(root + "/recipients", MAX_RECIPIENTS)
        return {"familyId": data["familyId"], "storage": "firestore",
                "recipients": sorted([public_recipient(r) for r in recipients], key=lambda r: r["createdAt"])}

    def add_recipient(self, uid, request):
        rid = "recipient-" + digest([uid, request.requestId])[:32]
        root, path, _ = self.paths(uid, rid)
        details = request.model_dump(exclude={"requestId", "acknowledgeSetup"})
        def add(state):
            owner_check(state[root], uid)
            existing = state[path]
            if existing:
                if existing["setupHash"] != digest(details):
                    raise FamilyError("This request was already used for different setup. Refresh before adding another recipient.", 409)
                return {}, None
            family = state[root]
            labels = family["recipientLabels"]
            if len(labels) >= MAX_RECIPIENTS:
                raise FamilyError("This family already has eight recipients.", 409)
            if details["label"].casefold() in labels:
                raise FamilyError("Use a different recipient label.", 409)
            family["recipientLabels"] = labels + [details["label"].casefold()]
            record = details | {"recipientId": rid, "createdAt": now(), "setupHash": digest(details), "importCount": 0}
            return {root: family, path: record}, None
        self.repo.transact([root, path], add)
        return self.get_family(uid)

    def _check(self, state, root, rec, uid):
        owner_check(state[root], uid)
        if not state[rec]:
            raise FamilyError("Recipient does not belong to this cloud family.", 404)

    def _scope(self, uid, rid):
        root, rec, _ = self.paths(uid, rid)
        self.repo.transact([root, rec], lambda state: (self._check(state, root, rec, uid) or {}, None))
        return root, rec

    def upload(self, uid, rid, request):
        # Reject foreign scope BEFORE decoding/Storage access.
        self._scope(uid, rid)
        raw, messages = decode_upload(request)
        metadata = request.model_dump(exclude={"fileBase64", "acknowledgeUpload"})
        sha = hashlib.sha256(raw).hexdigest()
        iid = digest({"sha256": sha, "metadata": metadata})
        root, rec, path = self.paths(uid, rid, iid)
        object_path = f"families/{family_id(uid)}/recipients/{rid}/imports/{iid}/original"
        record = metadata | {"importId": iid, "sha256": sha, "size": len(raw), "messageCount": len(messages),
                             "createdAt": now(), "uploadedBy": uid, "status": "upload_pending",
                             "objectPath": object_path, "bucket": settings.CLOUD_IMPORT_BUCKET,
                             "generation": None, "parserVersion": PARSER_VERSION, "revision": 0, "candidateExcerpts": []}
        def reserve(state):
            self._check(state, root, rec, uid)
            if state[path]:
                if state[path]["bucket"] != settings.CLOUD_IMPORT_BUCKET:
                    raise FamilyError("This import belongs to a different configured bucket. Restore the original bucket configuration.", 409)
                return {}, state[path]
            if state[rec]["importCount"] >= MAX_IMPORTS:
                raise FamilyError("This recipient has reached the 100-import limit. Contact the operator.", 409)
            state[rec]["importCount"] += 1
            return {rec: state[rec], path: record}, record
        existing = self.repo.transact([root, rec, path], reserve)
        if existing["status"] != "stored":
            generation = self.objects.put(object_path, raw, sha)
            def finish(state):
                self._check(state, root, rec, uid)
                saved = state[path]
                if saved["status"] == "stored" and saved["generation"] != generation:
                    raise FamilyError("The original file changed unexpectedly.", 409)
                saved.update(status="stored", generation=generation)
                return {path: saved}, None
            self.repo.transact([root, rec, path], finish)
        return self.inspect_import(uid, rid, iid)

    def _record(self, uid, rid, iid):
        root, rec, path = self.paths(uid, rid, iid)
        def read(state):
            self._check(state, root, rec, uid)
            if not state[path]:
                raise FamilyError("Import not found for this recipient.", 404)
            return {}, state[path]
        return self.repo.transact([root, rec, path], read)

    def _raw(self, record):
        if record["status"] != "stored":
            raise FamilyError("Upload is incomplete. Retry the same original file.", 409)
        if record["bucket"] != settings.CLOUD_IMPORT_BUCKET:
            raise FamilyError("This original is stored in another bucket. Ask the operator to restore the bucket configuration.", 409)
        return self.objects.get(record["objectPath"], record["generation"], record["sha256"], record["size"])

    def original(self, uid, rid, iid):
        record = self._record(uid, rid, iid)
        return self._raw(record), record["filename"]

    def messages(self, uid, rid, iid):
        record = self._record(uid, rid, iid)
        return {"messages": self._messages(record)}

    def _messages(self, record):
        if record.get("parserVersion") != PARSER_VERSION:
            raise FamilyError("This import uses a different parser version. Explicit reprocessing is required.", 409)
        return parse(self._raw(record), record)

    def review(self, uid, rid, iid, request):
        record = self._record(uid, rid, iid)
        if record["revision"] != request.revision:
            raise FamilyError("This review changed in another worker. Read it again before saving.", 409)
        messages = self._messages(record)
        if any(i >= len(messages) for i in request.sourceIndexes):
            raise FamilyError("A selected source message does not exist.")
        context = [messages[i] for i in sorted(request.sourceIndexes)]
        if any(len(m["text"]) > 500 for m in context):
            raise FamilyError("Each reviewed excerpt must contain at most 500 characters.")
        root, rec, path = self.paths(uid, rid, iid)
        def save(state):
            self._check(state, root, rec, uid)
            item = state[path]
            if item["revision"] != request.revision:
                raise FamilyError("This review changed in another worker. Read it again before saving.", 409)
            item.update(candidateExcerpts=context, reviewSha256=digest(context), reviewedAt=now(),
                        revision=item["revision"] + 1)
            return {path: item}, None
        self.repo.transact([root, rec, path], save)
        return self.inspect_import(uid, rid, iid)

    def inspect_import(self, uid, rid, iid):
        root, rec, path = self.paths(uid, rid, iid)
        def read(state):
            self._check(state, root, rec, uid)
            item = state[path]
            if not item:
                raise FamilyError("Import not found.", 404)
            result = {key: item[key] for key in ("importId", "filename", "source", "dateOrder", "timeZone",
                      "childSender", "parentSender", "size", "messageCount", "createdAt", "status", "revision", "candidateExcerpts")}
            # No trusted dual-consent producer or telephone consumer exists yet.
            # Even imported/forged approval fields must not activate anything.
            result.update(originalRetained=item["status"] == "stored", contextAuthorized=False,
                          contextStatus="inactive_pending_dual_consent")
            return {}, result
        return self.repo.transact([root, rec, path], read)

    def list_imports(self, uid, rid):
        _, rec = self._scope(uid, rid)
        records = self.repo.list(rec + "/imports", MAX_IMPORTS)
        return {"imports": sorted([self.inspect_import(uid, rid, item["importId"]) for item in records],
                                  key=lambda item: item["createdAt"], reverse=True)}

@contextmanager
def service():
    # Must fail before creating clients or consulting ADC on disabled/malformed
    # configuration. Firebase/local browser settings do not authorize this job.
    if not configured():
        raise FamilyError("Internal intake needs CLOUD_INTAKE_ENABLED, FIRESTORE_ENABLED, a project/database and an existing private CLOUD_IMPORT_BUCKET.", 403)
    from app.family.repository import FirestoreRepository
    from app.family.objects import PrivateObjects
    repo = FirestoreRepository()
    objects = None
    try:
        objects = PrivateObjects()
        yield FamilyService(repo, objects)
    finally:
        try:
            if objects:
                objects.close()
        finally:
            repo.close()
