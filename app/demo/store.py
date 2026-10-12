"""Local family membership and isolated per-recipient continuity, never cloud auth."""

import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import settings
from app.demo.models import (
    CreateFamily, CreateRecipient, ReviewBackground, SelectRecipientVoice,
    SetWellbeingSharing,
)
from app.memory.followups import FollowupState, expire, record_consent
from app.memory.failures import MEMORY_ERROR_CODES
from app.wellbeing.models import WellbeingSignalDraft, display_text

MAX_RECIPIENTS = 8


class DemoError(ValueError):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def now():
    return datetime.now(timezone.utc)


class DemoStore:
    def __init__(self, path=None, *, repository=None):
        from app.demo.repository import SQLiteFamilyRepository
        self.path = Path(path) if path is not None else None
        self.repository = repository or SQLiteFamilyRepository(self.path)

    def _run(self, mutate, *, uid=None, parent=None, create=False):
        def checked(state):
            if state:
                if state.get("schemaVersion") != 2:
                    raise DemoError("Unsupported demo data version; no call was started.")
                for recipient in state["recipients"]:
                    recipient.setdefault("wellbeingSharing", {"enabled": False, "generation": 0, "consentedAt": None})
                    recipient.setdefault("wellbeingSignals", [])
            return mutate(state)
        return self.repository.transact(self.owner(uid) if uid is not None else None, parent, checked, create=create)

    @staticmethod
    def owner(uid):
        return hashlib.sha256(f"local-demo:{uid}".encode()).hexdigest()

    @staticmethod
    def _recipient(state, recipient_id):
        for recipient in state["recipients"]:
            if recipient["recipientId"] == recipient_id:
                return recipient
        raise DemoError("Choose a recipient belonging to this demo family.", 404)

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
        recipient.setdefault("wellbeingSharing", {
            "enabled": False, "generation": 0, "consentedAt": None,
        })
        recipient.setdefault("wellbeingSignals", [])
        memory = FollowupState.model_validate(recipient["memory"])
        expire(memory, now())
        active = recipient.get("activeCall")
        return {key: recipient[key] for key in (
            "recipientId", "label", "relationship", "timeZone", "revision", "background", "calls", "voice",
        )} | {
            "language": recipient.get("language", "auto"),
            "legacy": recipient.get("legacy", False),
            "memoryEnabled": memory.consent and not memory.privacy_hold,
            "memoryCount": len(memory.concerns) if memory.consent and not memory.privacy_hold else 0,
            "memoryCooldownHours": settings.FOLLOWUP_COOLDOWN_HOURS,
            "busy": bool(active and active["leaseUntil"] > now().isoformat()),
            "wellbeingSharingEnabled": bool(recipient["wellbeingSharing"]["enabled"]),
            "wellbeingSignals": [
                {key: signal[key] for key in (
                    "signalId", "category", "confidence", "basis", "displayText",
                    "observedAt", "expiresAt", "policyVersion", "syntheticOnly",
                )}
                for signal in recipient["wellbeingSignals"]
                if signal["expiresAt"] > now().isoformat()
            ][-10:],
        }

    def public(self, state):
        return {key: state[key] for key in ("familyId", "childId", "expiresAt", "schemaVersion")} | {
            "syntheticOnly": True,
            "storageMode": settings.HUGBACK_DEMO_STORE,
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
            "language": request.language,
            "relationship": request.relationship, "timeZone": request.timeZone,
            "revision": 0, "background": [], "calls": [], "activeCall": None,
            "memory": memory.model_dump(mode="json"), "voice": {"mode": "standard", "profileId": None},
            "wellbeingSharing": {
                "enabled": request.enableWellbeingSharing,
                "generation": 1 if request.enableWellbeingSharing else 0,
                "consentedAt": now().isoformat() if request.enableWellbeingSharing else None,
            },
            "wellbeingSignals": [],
        }

    def create(self, uid: str, request: CreateFamily):
        def action(state):
            if not state:
                state.update({
                    "schemaVersion": 2, "familyId": f"demo-family-{uuid.uuid4().hex}",
                    "childId": f"demo-child-{uuid.uuid4().hex}",
                    "expiresAt": (now() + timedelta(days=7)).isoformat(),
                    "recipients": [self.new_recipient(request)],
                })
            return self.public(state)
        return self._run(action, uid=uid, create=True)

    def add_recipient(self, uid, request: CreateRecipient):
        def action(state):
            if len(state["recipients"]) >= MAX_RECIPIENTS:
                raise DemoError("Keep at most eight recipients in a local demo family.")
            if any(r["label"].casefold() == request.label.casefold() for r in state["recipients"]):
                raise DemoError("A recipient with this label already exists. Refresh the family.")
            state["recipients"].append(self.new_recipient(request))
            return self.public(state)
        return self._run(action, uid=uid)


    def get(self, uid):
        def action(state):
            for recipient in state["recipients"]:
                if not recipient.get("activeCall") or recipient["activeCall"]["leaseUntil"] <= now().isoformat():
                    self._check_idle(recipient)
                memory = FollowupState.model_validate(recipient["memory"])
                expire(memory, now())
                recipient["memory"] = memory.model_dump(mode="json")
                recipient["wellbeingSignals"] = [
                    signal for signal in recipient["wellbeingSignals"] if signal["expiresAt"] > now().isoformat()
                ]
            return self.public(state)
        return self._run(action, uid=uid)


    def _editable(self, state, recipient_id, revision):
        recipient = self._recipient(state, recipient_id)
        self._check_idle(recipient)
        if recipient["revision"] != revision:
            raise DemoError("This recipient's setup changed in another tab. Refresh before continuing.")
        return recipient

    def review(self, uid, request: ReviewBackground):
        def action(state):
            recipient = self._editable(state, request.recipientId, request.revision)
            recipient["background"] = [item.model_dump() | {
                "role": "child" if item.sender == request.childSender else "parent",
                "source": request.source, "reviewedAt": now().isoformat(),
            } for item in request.excerpts]
            recipient["revision"] += 1
            return self.public(state)
        return self._run(action, uid=uid)


    def clear(self, uid, recipient_id, revision):
        def action(state):
            recipient = self._editable(state, recipient_id, revision)
            recipient["background"] = []
            recipient["qualityReports"] = []
            recipient["revision"] += 1
            return self.public(state)
        return self._run(action, uid=uid)


    def select_voice(self, uid, request: SelectRecipientVoice):
        def action(state):
            recipient = self._editable(state, request.recipientId, request.revision)
            recipient["voice"] = {"mode": request.mode, "profileId": request.profileId}
            recipient["revision"] += 1
            return self.public(state)
        return self._run(action, uid=uid)


    def set_wellbeing_sharing(self, uid, request: SetWellbeingSharing):
        def action(state):
            recipient = self._editable(
                state, request.recipientId, request.revision,
            )
            sharing = recipient["wellbeingSharing"]
            if sharing["enabled"] == request.enabled:
                return self.public(state)
            sharing.update(
                enabled=request.enabled,
                generation=sharing["generation"] + 1,
                consentedAt=now().isoformat() if request.enabled else None,
            )
            # A new sharing decision never revives or carries forward old output.
            recipient["wellbeingSignals"] = []
            recipient["revision"] += 1
            return self.public(state)
        return self._run(action, uid=uid)


    def start_call(self, uid, session_id, recipient_id, revision, voice_profile_id=None):
        if not isinstance(recipient_id, str) or type(revision) is not int or revision < 0:
            raise DemoError("Explicit recipient selection and current setup revision are required.", 400)
        def action(state):
            recipient = self._editable(state, recipient_id, revision)
            selected_voice = recipient["voice"]
            if voice_profile_id != selected_voice["profileId"]:
                raise DemoError("This recipient's voice selection changed. Refresh before calling.")
            recipient["activeCall"] = {
                "sessionId": session_id, "leaseUntil": (now() + timedelta(minutes=12)).isoformat(),
            }
            recipient["calls"] = (recipient["calls"] + [{
                "sessionId": session_id, "startedAt": now().isoformat(), "status": "connecting",
            }])[-20:]
            # Preserve the broker/coordinator's internal parent-scoped contract.
            return {**recipient, "parentId": recipient_id, "familyId": state["familyId"], "childId": state["childId"]}
        return self._run(action, uid=uid)


    def call_status(self, parent, session_id, status, *, release=False, quality_pending=False,
                    memory_error=None):
        if memory_error is not None and memory_error not in MEMORY_ERROR_CODES:
            raise DemoError("Invalid memory failure category")
        def action(state):
            recipient = self._recipient(state, parent)
            active = recipient.get("activeCall")
            if not active or active["sessionId"] != session_id:
                return False
            if status == "active" and active["leaseUntil"] <= now().isoformat():
                return False
            for call in recipient["calls"]:
                if call["sessionId"] == session_id:
                    call["status"] = status
                    if status == "memory_failed":
                        call["memoryErrorCode"] = memory_error or "processing_failed"
                    else:
                        call.pop("memoryErrorCode", None)
                    if release:
                        call["endedAt"] = now().isoformat()
                        if quality_pending:
                            call.setdefault("workflow", {})["critic"] = "pending"
            if release:
                recipient["activeCall"] = None
            return True
        return self._run(action, parent=parent)


    def record_wellbeing_signal(
        self, parent, session_id, expected_generation, draft: WellbeingSignalDraft,
        *, model: str, retention_hours=72,
    ):
        """Commit one bounded signal after rechecking recipient, call and consent."""
        def action(state):
            recipient = self._recipient(state, parent)
            sharing = recipient["wellbeingSharing"]
            active = recipient.get("activeCall")
            if (
                not sharing["enabled"] or sharing["generation"] != expected_generation
                or not active or active["sessionId"] != session_id
                or draft.category == "unclear" or draft.confidence == "low"
            ):
                return False
            if any(item["sessionId"] == session_id for item in recipient["wellbeingSignals"]):
                return False
            created = now()
            recipient["wellbeingSignals"] = [
                item for item in recipient["wellbeingSignals"] if item["expiresAt"] > created.isoformat()
            ][-9:] + [{
                "signalId": f"signal-{uuid.uuid4().hex}",
                "sessionId": session_id,
                "category": draft.category,
                "confidence": draft.confidence,
                "basis": list(dict.fromkeys(draft.basis)),
                "displayText": display_text(draft.category),
                "observedAt": created.isoformat(),
                "expiresAt": (created + timedelta(hours=retention_hours)).isoformat(),
                "policyVersion": "wellbeing-signal-v1",
                "modelVersion": model[:100],
                "syntheticOnly": True,
            }]
            return True
        return self._run(action, parent=parent)


    def revoke_wellbeing_sharing(self, parent, expected_generation):
        """Honor an in-call don't-share request without altering memory consent."""
        def action(state):
            recipient = self._recipient(state, parent)
            sharing = recipient["wellbeingSharing"]
            if sharing["generation"] != expected_generation:
                return False
            sharing.update(enabled=False, generation=sharing["generation"] + 1, consentedAt=None)
            recipient["wellbeingSignals"] = []
            recipient["qualityReports"] = []
            recipient["revision"] += 1  # Invalidate in-flight reviews after don't-share intent.
            return True
        return self._run(action, parent=parent)


    def forget_background(self, parent):
        def action(state):
            recipient = self._recipient(state, parent)
            recipient["background"] = []
            recipient["qualityReports"] = []
            recipient["revision"] += 1

        return self._run(action, parent=parent)


    async def transact(self, parent, mutate):
        def action(state):
            recipient = self._recipient(state, parent)
            memory = FollowupState.model_validate(recipient["memory"])
            generation = memory.generation
            result = mutate(memory)
            if memory.generation != generation:
                recipient["qualityReports"] = []
            recipient["memory"] = memory.model_dump(mode="json")
            return result
        return await asyncio.to_thread(self._run, action, parent=parent)

    def workflow_checkpoint(self, parent, session, stages, *, report=None, revision=None, generation=None):
        """Bounded status is public. Content-free critic findings stay internal."""
        allowed = {"planner", "reconciler", "critic"}
        statuses = {"ready", "fallback", "processed", "skipped", "failed", "completed",
                    "privacy_skipped", "privacy_hold", "revoked", "pending", "already_processed"}
        if not set(stages) <= allowed or any(value not in statuses for value in stages.values()):
            raise DemoError("Invalid workflow checkpoint")
        def action(state):
            recipient = self._recipient(state, parent)
            call = next((c for c in recipient["calls"] if c["sessionId"] == session), None)
            if call is None:
                return False
            if report is not None and (
                recipient["revision"] != revision
                or recipient["memory"]["generation"] != generation
            ):
                call.setdefault("workflow", {})["critic"] = "privacy_skipped"
                return False
            call.setdefault("workflow", {}).update(stages)
            if report is not None:
                reports = [r for r in recipient.get("qualityReports", []) if r["sessionId"] != session]
                recipient["qualityReports"] = (reports + [{
                    "sessionId": session, "version": "critic-v1",
                    "model": settings.FOLLOWUP_EXTRACTION_MODEL[:100],
                    "observedAt": now().isoformat(), "uncertain": report.uncertain,
                    "findings": [{"code": f.code, "severity": f.severity, "sourceTurn": f.source_turn}
                                 for f in report.findings],
                }])[-20:]
            return True
        return self._run(action, parent=parent)

    def inspect_quality(self, uid, recipient_id):
        """Trusted operator CLI only; deliberately no browser route."""
        return self._run(lambda state: self._recipient(state, recipient_id).get("qualityReports", []), uid=uid)

    async def quality_eligible(self, parent, revision, generation):
        def check(state):
            recipient = self._recipient(state, parent)
            return (recipient["revision"] == revision and recipient["memory"]["generation"] == generation
                    and not recipient["memory"].get("privacy_hold"))
        return await asyncio.to_thread(self._run, check, parent=parent)
