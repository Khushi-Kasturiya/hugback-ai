"""Local family membership and isolated per-recipient continuity, never cloud auth."""

import asyncio
import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import settings
from app.demo.models import CreateFamily, CreateRecipient, ReviewBackground, SelectRecipientVoice
from app.memory.followups import FollowupState, expire, record_consent

MAX_RECIPIENTS = 8


class DemoError(ValueError):
    def __init__(self, message: str, status=409):
        super().__init__(message)
        self.status = status


def now():
    return datetime.now(timezone.utc)


class DemoStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        conn = sqlite3.connect(self.path, timeout=5)
        os.chmod(self.path, 0o600)
        try:
            # Retain the old parent column as a migration anchor, not a selector.
            conn.execute("CREATE TABLE IF NOT EXISTS families "
                         "(owner TEXT PRIMARY KEY, parent TEXT UNIQUE NOT NULL, state TEXT NOT NULL)")
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM families WHERE json_extract(state, '$.expiresAt') <= ?", (now().isoformat(),))
            # Transactional, idempotent v1 migration. Never guess whether old mixed
            # history belonged to Mother/Father or duplicate it into new recipients.
            for owner, raw in conn.execute("SELECT owner, state FROM families WHERE json_extract(state, '$.schemaVersion') IS NULL").fetchall():
                state = json.loads(raw)
                recipient = {key: state[key] for key in (
                    "timeZone", "revision", "background", "calls", "activeCall", "memory",
                )}
                recipient.update(recipientId=state["parentId"], label="Existing parent", relationship="other",
                                 legacy=True, voice={"mode": "standard", "profileId": None})
                migrated = {key: state[key] for key in ("familyId", "childId", "expiresAt")}
                migrated.update(schemaVersion=2, recipients=[recipient])
                conn.execute("UPDATE families SET state=? WHERE owner=?", (json.dumps(migrated), owner))
            conn.commit()
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def owner(uid):
        return hashlib.sha256(f"local-demo:{uid}".encode()).hexdigest()

    def _row(self, conn, uid=None, parent=None):
        if uid is not None:
            row = conn.execute("SELECT owner, state FROM families WHERE owner=?", (self.owner(uid),)).fetchone()
        else:
            # Internal finalizers receive only a server-resolved, immutable recipient
            # ID. Public callers must ALWAYS take the owner + membership path below.
            row = conn.execute("""SELECT owner, state FROM families WHERE EXISTS (
                SELECT 1 FROM json_each(state, '$.recipients')
                WHERE json_extract(value, '$.recipientId') = ?
            )""", (parent,)).fetchone()
        if not row:
            raise DemoError("Create a synthetic demo family in Child setup first.", 404)
        state = json.loads(row[1])
        if state.get("schemaVersion") != 2:
            raise DemoError("Unsupported demo data version; no call was started.")
        return row[0], state

    @staticmethod
    def _recipient(state, recipient_id):
        for recipient in state["recipients"]:
            if recipient["recipientId"] == recipient_id:
                return recipient
        raise DemoError("Choose a recipient belonging to this demo family.", 404)

    @staticmethod
    def _save(conn, owner, state):
        conn.execute("UPDATE families SET state=? WHERE owner=?", (json.dumps(state), owner))

    @staticmethod
    def _check_idle(recipient):
        active = recipient.get("activeCall")
        if active and active["leaseUntil"] > now().isoformat():
            raise DemoError("This recipient's previous call is active or still saving memory. Wait, then retry.")
        if active:
            for call in recipient["calls"]:
                if call["sessionId"] == active["sessionId"]:
                    call["status"] = "interrupted"
            recipient["activeCall"] = None

    @staticmethod
    def public_recipient(recipient):
        memory = FollowupState.model_validate(recipient["memory"])
        expire(memory, now())
        active = recipient.get("activeCall")
        return {key: recipient[key] for key in (
            "recipientId", "label", "relationship", "timeZone", "revision", "background", "calls", "voice",
        )} | {
            "legacy": recipient.get("legacy", False),
            "memoryEnabled": memory.consent and not memory.privacy_hold,
            "memoryCount": len(memory.concerns) if memory.consent and not memory.privacy_hold else 0,
            "memoryCooldownHours": settings.FOLLOWUP_COOLDOWN_HOURS,
            "busy": bool(active and active["leaseUntil"] > now().isoformat()),
        }

    def public(self, state):
        return {key: state[key] for key in ("familyId", "childId", "expiresAt", "schemaVersion")} | {
            "syntheticOnly": True,
            "recipients": [self.public_recipient(recipient) for recipient in state["recipients"]],
        }

    @staticmethod
    def new_recipient(request: CreateRecipient):
        memory = FollowupState(time_zone=request.timeZone)
        if request.enableMemory:
            record_consent(memory, version="synthetic-demo-v1", source="local_simulator_not_verified_parent",
                           time_zone=request.timeZone, now=now())
        return {
            "recipientId": f"demo-parent-{uuid.uuid4().hex}", "label": request.label,
            "relationship": request.relationship, "timeZone": request.timeZone,
            "revision": 0, "background": [], "calls": [], "activeCall": None,
            "memory": memory.model_dump(mode="json"), "voice": {"mode": "standard", "profileId": None},
        }

    def create(self, uid: str, request: CreateFamily):
        with self.connection() as conn:
            existing = conn.execute("SELECT state FROM families WHERE owner=?", (self.owner(uid),)).fetchone()
            if existing:
                return self.public(json.loads(existing[0]))
            recipient = self.new_recipient(request)
            state = {
                "schemaVersion": 2, "familyId": f"demo-family-{uuid.uuid4().hex}",
                "childId": f"demo-child-{uuid.uuid4().hex}",
                "expiresAt": (now() + timedelta(days=7)).isoformat(), "recipients": [recipient],
            }
            conn.execute("INSERT INTO families VALUES (?,?,?)",
                         (self.owner(uid), recipient["recipientId"], json.dumps(state)))
            return self.public(state)

    def add_recipient(self, uid, request: CreateRecipient):
        with self.connection() as conn:
            owner, state = self._row(conn, uid=uid)
            if len(state["recipients"]) >= MAX_RECIPIENTS:
                raise DemoError("Keep at most eight recipients in a local demo family.")
            if any(r["label"].casefold() == request.label.casefold() for r in state["recipients"]):
                raise DemoError("A recipient with this label already exists. Refresh the family.")
            state["recipients"].append(self.new_recipient(request))
            self._save(conn, owner, state)
            return self.public(state)

    def get(self, uid):
        with self.connection() as conn:
            owner, state = self._row(conn, uid=uid)
            for recipient in state["recipients"]:
                if not recipient.get("activeCall") or recipient["activeCall"]["leaseUntil"] <= now().isoformat():
                    self._check_idle(recipient)
                memory = FollowupState.model_validate(recipient["memory"])
                expire(memory, now())
                recipient["memory"] = memory.model_dump(mode="json")
            self._save(conn, owner, state)
            return self.public(state)

    def _editable(self, conn, uid, recipient_id, revision):
        owner, state = self._row(conn, uid=uid)
        recipient = self._recipient(state, recipient_id)
        self._check_idle(recipient)
        if recipient["revision"] != revision:
            raise DemoError("This recipient's setup changed in another tab. Refresh before continuing.")
        return owner, state, recipient

    def review(self, uid, request: ReviewBackground):
        with self.connection() as conn:
            owner, state, recipient = self._editable(conn, uid, request.recipientId, request.revision)
            recipient["background"] = [item.model_dump() | {
                "role": "child" if item.sender == request.childSender else "parent",
                "source": request.source, "reviewedAt": now().isoformat(),
            } for item in request.excerpts]
            recipient["revision"] += 1
            self._save(conn, owner, state)
            return self.public(state)

    def clear(self, uid, recipient_id, revision):
        with self.connection() as conn:
            owner, state, recipient = self._editable(conn, uid, recipient_id, revision)
            recipient["background"] = []
            recipient["revision"] += 1
            self._save(conn, owner, state)
            return self.public(state)

    def select_voice(self, uid, request: SelectRecipientVoice):
        with self.connection() as conn:
            owner, state, recipient = self._editable(conn, uid, request.recipientId, request.revision)
            recipient["voice"] = {"mode": request.mode, "profileId": request.profileId}
            recipient["revision"] += 1
            self._save(conn, owner, state)
            return self.public(state)

    def start_call(self, uid, session_id, recipient_id, revision, voice_profile_id=None):
        if not isinstance(recipient_id, str) or type(revision) is not int or revision < 0:
            raise DemoError("Explicit recipient selection and current setup revision are required.", 400)
        with self.connection() as conn:
            owner, state, recipient = self._editable(conn, uid, recipient_id, revision)
            selected_voice = recipient["voice"]
            if voice_profile_id != selected_voice["profileId"]:
                raise DemoError("This recipient's voice selection changed. Refresh before calling.")
            recipient["activeCall"] = {
                "sessionId": session_id, "leaseUntil": (now() + timedelta(minutes=12)).isoformat(),
            }
            recipient["calls"] = (recipient["calls"] + [{
                "sessionId": session_id, "startedAt": now().isoformat(), "status": "connecting",
            }])[-20:]
            self._save(conn, owner, state)
            # Preserve the broker/coordinator's internal parent-scoped contract.
            return {**recipient, "parentId": recipient_id, "familyId": state["familyId"], "childId": state["childId"]}

    def call_status(self, parent, session_id, status, *, release=False):
        with self.connection() as conn:
            owner, state = self._row(conn, parent=parent)
            recipient = self._recipient(state, parent)
            active = recipient.get("activeCall")
            if not active or active["sessionId"] != session_id:
                return False
            if status == "active" and active["leaseUntil"] <= now().isoformat():
                return False
            for call in recipient["calls"]:
                if call["sessionId"] == session_id:
                    call["status"] = status
                    if release:
                        call["endedAt"] = now().isoformat()
            if release:
                recipient["activeCall"] = None
            self._save(conn, owner, state)
            return True

    def forget_background(self, parent):
        with self.connection() as conn:
            owner, state = self._row(conn, parent=parent)
            recipient = self._recipient(state, parent)
            recipient["background"] = []
            recipient["revision"] += 1
            self._save(conn, owner, state)

    async def transact(self, parent, mutate):
        def run():
            with self.connection() as conn:
                owner, state = self._row(conn, parent=parent)
                recipient = self._recipient(state, parent)
                memory = FollowupState.model_validate(recipient["memory"])
                result = mutate(memory)
                recipient["memory"] = memory.model_dump(mode="json")
                self._save(conn, owner, state)
                return result
        return await asyncio.to_thread(run)
