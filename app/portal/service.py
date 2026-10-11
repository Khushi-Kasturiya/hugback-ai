"""Read-only adapter for parent-approved, recipient-scoped updates.

No public write/grant endpoint exists. Trusted phone enrollment and the
exact-content approval producer are release gates, not implied by this reader.
"""
import asyncio
import hashlib
import inspect
from datetime import datetime, timezone

from app.config import settings


def owner_key(uid: str) -> str:
    return hashlib.sha256(uid.encode()).hexdigest()


def _time(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    return value


def valid_relationship(data: dict, uid: str, now: datetime) -> bool:
    verified = _time(data.get("verified_at"))
    expires = _time(data.get("expires_at"))
    return bool(
        data.get("child_uid") == uid and data.get("status") == "verified"
        and isinstance(data.get("parent_id"), str) and data["parent_id"]
        and type(data.get("generation")) is int and data["generation"] >= 1
        and verified and expires and verified <= now < expires
    )


def visible_summary(doc_id: str, data: dict, relationship: dict, uid: str, now: datetime):
    if not valid_relationship(relationship, uid, now):
        return None
    text = data.get("approved_text")
    ended = _time(data.get("call_ended_at"))
    approved = _time(data.get("approved_at"))
    expires = _time(data.get("expires_at"))
    if not (
        data.get("child_uid") == uid and data.get("parent_id") == relationship["parent_id"]
        and data.get("relationship_generation") == relationship["generation"]
        and data.get("status") == "approved" and data.get("approval_source") == "verified_parent"
        and isinstance(text, str) and 1 <= len(text) <= 2000
        and data.get("approved_text_sha256") == hashlib.sha256(text.encode()).hexdigest()
        and ended and approved and expires and ended <= approved <= now < expires
    ):
        return None
    return {
        "id": doc_id, "text": text,
        "callEndedAt": ended.isoformat(), "approvedAt": approved.isoformat(),
        "expiresAt": min(expires, relationship["expires_at"]).isoformat(),
    }


def _new_client():
    from google.cloud import firestore
    return firestore.AsyncClient(
        project=settings.GOOGLE_CLOUD_PROJECT, database=settings.FIRESTORE_DATABASE,
    )


async def read_shared_summaries(uid: str) -> dict:
    # A single bounded mailbox document makes link revocation and update reads
    # consistent. Cloud IAM must deny client-side writes to this collection.
    async def read():
        client = _new_client()
        try:
            snapshot = await client.collection("child_portal_mailboxes").document(owner_key(uid)).get()
            data = snapshot.to_dict() if snapshot.exists else {}
            relationship = data.get("relationship", {})
            now = datetime.now(timezone.utc)
            if not isinstance(relationship, dict) or not valid_relationship(relationship, uid, now):
                return {"status": "awaiting_parent_link", "summaries": []}
            records = data.get("updates", [])
            if not isinstance(records, list) or len(records) > 50:
                raise ValueError("Mailbox exceeds its bounded schema")
            visible = []
            for record in records:
                if not isinstance(record, dict):
                    continue
                doc_id = record.get("id")
                if not isinstance(doc_id, str) or not doc_id:
                    continue
                item = visible_summary(doc_id, record, relationship, uid, now)
                if item:
                    visible.append(item)
            return {"status": "ready", "summaries": sorted(visible, key=lambda s: s["callEndedAt"], reverse=True)}
        finally:
            closed = client.close()
            if inspect.isawaitable(closed):
                await closed

    return await asyncio.wait_for(read(), timeout=5)
