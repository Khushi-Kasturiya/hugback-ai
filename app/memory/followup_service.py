"""Call orchestration around canonical follow-ups; fail closed on memory errors."""

import re
import hashlib
from datetime import timedelta
from typing import Protocol

from app.config import settings
from app.memory.followups import (
    TOPICS, CallPlan, FollowupState, ObservationBatch, apply_observations,
    claim, expire, mark_output, reserve, revoke, utc_now,
    record_consent,
)
from app.memory.followup_store import FollowupStore
from app.memory.models import TranscriptTurn

# Conservative privacy intent checks. Exact evidence must ALSO come from the
# latest user utterance, never retrieved memory or the assistant's text.
_FORGET = re.compile(r"\b(forget|do not remember|don't remember|dont remember|yaad mat|yaad nahi|bhool)\b|याद मत|मत याद|भूल", re.I)
_SUPPRESS = re.compile(r"\b(do not ask|don't ask|dont ask|stop asking|mat (?:puch|pooch)\w*)\b|मत पूछ", re.I)
_ALL = re.compile(r"\b(everything|all memories|all memory|sab kuch)\b|सब कुछ", re.I)
_TOPIC_WORDS = {
    "fever": ("fever", "bukhar", "बुखार"),
    "sleep": ("sleep", "neend", "नींद"),
    "appetite": ("appetite", "bhook", "भूख"),
    "energy": ("energy", "tired", "thakan", "थकान"),
    "physical_comfort": ("pain", "comfort", "dard", "दर्द"),
}


def contains_privacy_request(turns: list[TranscriptTurn]) -> bool:
    """Conservative hold signal, never a consent/permission grant."""
    return any(t.role == "user" and (_FORGET.search(t.text) or _SUPPRESS.search(t.text)) for t in turns)


class Extractor(Protocol):
    async def extract(self, turns: list[TranscriptTurn], plan: CallPlan) -> ObservationBatch: ...


class FollowupCoordinator:
    def __init__(self, store: FollowupStore, extractor: Extractor, *, cooldown_hours=24, retention_hours=72):
        self.store = store
        self.extractor = extractor
        # Product defaults, not medical thresholds.
        self.cooldown = timedelta(hours=cooldown_hours)
        self.retention = timedelta(hours=retention_hours)

    async def begin(self, owner: str, session: str, *, now=None) -> CallPlan:
        now = now or utc_now()
        return await self.store.transact(owner, lambda state: reserve(state, session, now, self.cooldown))

    async def record_verified_consent(self, owner, *, version, source, time_zone, now=None):
        """Called only by a trusted, verified-parent enrollment adapter.

        This method is deliberately NOT exposed to callers or Live tools.
        No enrollment/telephone identity verification is implemented here.
        """
        now = now or utc_now()
        await self.store.transact(owner, lambda state: record_consent(
            state, version=version, source=source, time_zone=time_zone, now=now,
        ))

    async def claim(self, owner: str, plan: CallPlan, *, latest_user_text="", now=None) -> dict:
        now = now or utc_now()
        if plan.selected and any(
            word in latest_user_text.lower() for word in _TOPIC_WORDS[plan.selected.topic]
        ):
            # Conservative deterministic guard: if the parent already brought
            # up the selected topic, follow their lead instead of re-prompting.
            plan.blocked_this_call = True
        result = await self.store.transact(owner, lambda state: claim(state, plan, now))
        if result["allowed"]:
            plan.claimed = True
        return result

    async def output(self, owner: str, plan: CallPlan, *, interrupted=False, now=None) -> None:
        if not plan.claimed or (plan.generated and not interrupted):
            return
        now = now or utc_now()
        if not interrupted:
            # Don't stall every PCM chunk by retrying an unavailable checkpoint.
            plan.generated = True
        await self.store.transact(
            owner, lambda state: mark_output(state, plan, now, interrupted=interrupted)
        )

    async def control(
        self, owner: str, plan: CallPlan, action: str, topic: str | None,
        evidence: str, latest_user_text: str,
    ) -> dict:
        """Privacy-only mutations; no model tool can enable/re-enable memory."""
        if not isinstance(evidence, str) or not evidence.strip() or evidence not in latest_user_text:
            return {"changed": False, "reason": "No matching current user evidence; ask for clarification."}
        if action not in ("suppress", "forget", "revoke_all"):
            return {"changed": False, "reason": "Unknown privacy action"}
        intent = _SUPPRESS if action == "suppress" else _FORGET
        if not intent.search(evidence) or (action == "revoke_all" and not _ALL.search(evidence)):
            return {"changed": False, "reason": "Explicit privacy instruction required; do not claim success."}
        if action != "revoke_all" and topic not in TOPICS:
            return {"changed": False, "reason": "Clarify which topic to stop or forget."}
        if action != "revoke_all":
            explicit_topic = any(word in evidence.lower() for word in _TOPIC_WORDS[topic])
            selected_topic = plan.selected.topic if plan.selected else None
            if not explicit_topic and topic != selected_topic:
                return {"changed": False, "reason": "Topic not grounded in current words or the selected follow-up."}

        def mutate(state: FollowupState):
            if action == "revoke_all":
                revoke(state)
            else:
                state.generation += 1
                state.concerns.pop(topic, None)
                if topic not in state.blocked_topics:
                    state.blocked_topics.append(topic)
            return {"changed": True, "action": action, "guidance": "Do not raise this remembered topic again."}

        result = await self.store.transact(owner, mutate)
        # Do not update plan.generation: all subsequent writes from this call's
        # pre-control transcript must be discarded, including in-flight workers.
        plan.selected = None
        return result

    async def finish(self, owner: str, plan: CallPlan, turns: list[TranscriptTurn], *, now=None) -> str:
        if not plan.consent or not any(t.role == "user" for t in turns):
            return "skipped"
        now = now or utc_now()

        def authorized(state):
            return state.consent and not state.privacy_hold and state.generation == plan.generation

        if not await self.store.transact(owner, authorized):
            return "revoked"
        # Never send a transcript containing an unhandled privacy instruction
        # to extraction. Withhold future retrieval until trusted clarification.
        # Successful in-call controls already changed generation above.
        if contains_privacy_request(turns):
            def hold(state):
                if state.generation == plan.generation:
                    state.privacy_hold = True
                    state.generation += 1
            await self.store.transact(owner, hold)
            return "privacy_hold"
        receipt = hashlib.sha256(plan.session_id.encode()).hexdigest()
        def start(state):
            expire(state, now)
            if not authorized(state):
                return "revoked"
            if receipt in state.processed_sessions:
                return "already_processed"
            if receipt in state.pending_sessions or len(state.pending_sessions) >= 8:
                return "pending"
            state.pending_sessions[receipt] = now + timedelta(seconds=30)
            return "started"
        status = await self.store.transact(owner, start)
        if status != "started":
            return status
        try:
            batch = await self.extractor.extract(turns, plan)
            await self.store.transact(
                owner, lambda state: apply_observations(
                    state, plan, turns, batch, now, self.retention, self.cooldown
                )
            )
        finally:
            await self.store.transact(owner, lambda state: state.pending_sessions.pop(receipt, None))
        return "processed"

    async def inspect(self, owner: str, *, now=None) -> dict:
        now = now or utc_now()
        def read(state):
            expire(state, now)
            return {
                "consent": state.consent, "privacy_hold": state.privacy_hold,
                "concerns": [
                    c.model_dump(mode="json") for c in state.concerns.values()
                ] if state.consent and not state.privacy_hold else [],
            }
        return await self.store.transact(owner, read)

    async def delete_all(self, owner: str) -> None:
        # Preserve the generation tombstone even when session docs are deleted.
        await self.store.transact(owner, revoke)


_coordinator = None


def get_followup_coordinator(*, privacy_operation=False) -> FollowupCoordinator | None:
    global _coordinator
    if not settings.FOLLOWUPS_ENABLED and not privacy_operation:
        return None
    if not settings.FIRESTORE_ENABLED:
        # Configuration being disabled does not prove remote records are gone.
        # Privacy APIs must not report a confirmed deletion without the store.
        raise RuntimeError("Follow-ups require explicitly enabled Firestore")
    if _coordinator is None:
        from app.memory.followup_extractor import GoogleFollowupExtractor
        from app.memory.followup_store import FirestoreFollowupStore
        _coordinator = FollowupCoordinator(
            FirestoreFollowupStore(settings.GOOGLE_CLOUD_PROJECT, settings.FIRESTORE_DATABASE),
            GoogleFollowupExtractor(),
            cooldown_hours=settings.FOLLOWUP_COOLDOWN_HOURS,
            retention_hours=settings.FOLLOWUP_RETENTION_HOURS,
        )
    return _coordinator
