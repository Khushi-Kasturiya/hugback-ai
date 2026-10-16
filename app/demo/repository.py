"""Transactional synthetic-family repositories. Never production family records.

Callbacks may be retried by Firestore; they contain only deterministic domain
work (no providers, audio, or network side effects). No SQLite/cloud fallback.
"""
import copy
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Protocol, TypeVar
from datetime import datetime, timezone

T = TypeVar("T")

def now():
    return datetime.now(timezone.utc)

class FamilyRepository(Protocol):
    def transact(self, owner: str | None, recipient: str | None,
                 mutate: Callable[[dict], T], *, create: bool = False) -> T: ...

class SQLiteFamilyRepository:
    def __init__(self, path):
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


    def transact(self, owner, recipient, mutate, *, create=False):
        from app.demo.store import DemoError
        with self.connection() as conn:
            if owner is not None:
                row = conn.execute("SELECT owner, state FROM families WHERE owner=?", (owner,)).fetchone()
            else:
                row = conn.execute("SELECT owner, state FROM families WHERE EXISTS ("
                    "SELECT 1 FROM json_each(state, '$.recipients') "
                    "WHERE json_extract(value, '$.recipientId') = ?)", (recipient,)).fetchone()
            if not row and not create:
                raise DemoError("Create a synthetic demo family first.", 404)
            state = json.loads(row[1]) if row else {}
            result = mutate(state)
            key = row[0] if row else owner
            if row:
                conn.execute("UPDATE families SET state=? WHERE owner=?", (json.dumps(state), key))
            else:
                conn.execute("INSERT INTO families VALUES (?,?,?)",
                    (key, state["recipients"][0]["recipientId"], json.dumps(state)))
            return copy.deepcopy(result)

class FirestoreFamilyRepository:
    # Fixed, separate collections; callers cannot select arbitrary collection paths.
    # Family metadata and recipient state are separate documents so independent
    # Mother/Father calls do not continually rewrite one growing aggregate.
    FAMILIES = "hugback_synthetic_test_families"
    RECIPIENTS = "hugback_synthetic_test_recipients"

    def __init__(self, project, database, *, client=None):
        from google.cloud import firestore
        self.firestore = firestore
        self.client = client or firestore.Client(project=project, database=database)

    def transact(self, owner, recipient, mutate, *, create=False):
        from app.demo.store import DemoError
        if owner is not None and not re.fullmatch(r"[a-f0-9]{64}", owner):
            raise DemoError("Invalid test owner", 403)
        if recipient is not None and not re.fullmatch(r"demo-parent-[a-f0-9]{32}", recipient):
            raise DemoError("Invalid test recipient", 403)
        @self.firestore.transactional
        def run(tx):
            key = owner
            recipient_scoped = owner is None
            selected_snapshot = None
            if key is None:
                selected_snapshot = self.client.collection(self.RECIPIENTS).document(recipient).get(transaction=tx).to_dict()
                index = selected_snapshot
                if not index or not index.get("syntheticOnly"):
                    raise DemoError("Unknown synthetic recipient", 404)
                key = index["owner"]
                if not re.fullmatch(r"[a-f0-9]{64}", key):
                    raise DemoError("Invalid test owner", 403)
            ref = self.client.collection(self.FAMILIES).document(key)
            saved = ref.get(transaction=tx).to_dict()
            if saved and (saved.get("syntheticOnly") is not True or saved.get("owner") != key):
                raise DemoError("Not a synthetic test family", 403)
            saved_state = copy.deepcopy(saved.get("state", {})) if saved else {}
            legacy_recipients = saved_state.pop("recipients", []) if saved_state else []
            recipient_ids = list(saved.get("recipientIds", [])) if saved else []
            if not recipient_ids:
                recipient_ids = [item["recipientId"] for item in legacy_recipients]
            if recipient is not None and recipient not in recipient_ids and selected_snapshot:
                # A recipient index without membership in its owning family is
                # stale and cannot revive or join a family.
                raise DemoError("Unknown synthetic recipient", 404)

            loaded_ids = [recipient] if recipient_scoped else recipient_ids
            snapshots = {}
            for recipient_id in loaded_ids:
                if recipient_id == recipient and selected_snapshot is not None:
                    item = selected_snapshot
                else:
                    item = self.client.collection(self.RECIPIENTS).document(recipient_id).get(transaction=tx).to_dict()
                if item and (item.get("owner") != key or item.get("syntheticOnly") is not True):
                    raise DemoError("Invalid synthetic recipient scope", 403)
                snapshots[recipient_id] = item or {}

            legacy_by_id = {item["recipientId"]: item for item in legacy_recipients}
            recipients = []
            for recipient_id in loaded_ids:
                record = snapshots[recipient_id].get("state") or legacy_by_id.get(recipient_id)
                if not isinstance(record, dict) or record.get("recipientId") != recipient_id:
                    raise DemoError("Synthetic recipient state is unavailable", 503)
                recipients.append(copy.deepcopy(record))

            state = saved_state | ({"recipients": recipients} if saved else {})
            if state and state["expiresAt"] <= now().isoformat():
                state = {}  # Old recipient references must never revive an expired family.
            if not state and not create:
                raise DemoError("Create a synthetic demo family first.", 404)
            if recipient is not None and not any(r["recipientId"] == recipient for r in state.get("recipients", [])):
                raise DemoError("Unknown synthetic recipient", 404)
            before = copy.deepcopy(state)
            result = mutate(state)
            if len(json.dumps(state).encode()) > 700_000:
                raise DemoError("Synthetic family exceeded its storage bound")
            if state != before:
                next_recipients = state["recipients"]
                next_ids = [item["recipientId"] for item in next_recipients]
                if len(next_ids) != len(set(next_ids)):
                    raise DemoError("Duplicate synthetic recipient")
                family_state = copy.deepcopy(state)
                family_state.pop("recipients", None)
                before_family = copy.deepcopy(before)
                before_family.pop("recipients", None)
                if recipient_scoped:
                    if family_state != before_family or next_ids != [recipient]:
                        raise DemoError("Recipient-scoped transaction cannot change family membership")
                    item = next_recipients[0]
                    if item != before["recipients"][0] or not snapshots[recipient].get("state"):
                        tx.set(self.client.collection(self.RECIPIENTS).document(recipient),
                               {"owner": key, "syntheticOnly": True, "state": item})
                    return copy.deepcopy(result)
                normalized = bool(saved and "recipientIds" in saved and not legacy_recipients)
                if family_state != before_family or next_ids != recipient_ids or not normalized:
                    tx.set(ref, {"syntheticOnly": True, "owner": key, "state": family_state,
                                 "recipientIds": next_ids,
                                 "expiresAt": datetime.fromisoformat(state["expiresAt"])})
                before_recipients = {item["recipientId"]: item for item in before.get("recipients", [])}
                for item in next_recipients:
                    recipient_id = item["recipientId"]
                    if item != before_recipients.get(recipient_id) or not snapshots.get(recipient_id, {}).get("state"):
                        tx.set(self.client.collection(self.RECIPIENTS).document(recipient_id),
                               {"owner": key, "syntheticOnly": True, "state": item})
            return copy.deepcopy(result)
        return run(self.client.transaction(max_attempts=5))
