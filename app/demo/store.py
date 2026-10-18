"""Local family membership and isolated per-recipient continuity, never cloud auth."""

import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import settings
from app.demo.models import (
    CreateFamily, CreateRecipient, SetChildGender, ReviewBackground, SelectRecipientVoice,
    SetWellbeingSharing, SetToneContinuity, SetTranscriptSharing, SetAlertSharing, SetAlertDestination,
)
from app.memory.followups import FollowupState, expire, record_consent
from app.memory.failures import MEMORY_ERROR_CODES
from app.wellbeing.models import WellbeingSignalDraft, display_text
from app.alerts.email import configured as alert_email_configured, valid_destination

MAX_RECIPIENTS = 8
MAX_TRANSCRIPT_CHARS = 25_000
MAX_TRANSCRIPT_TURNS = 250


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
                    recipient["voice"].pop("speakingForm", None)
                    recipient.setdefault("wellbeingSharing", {"enabled": False, "generation": 0, "consentedAt": None})
                    recipient.setdefault("wellbeingSignals", [])
                    recipient.setdefault("toneContinuity", {"enabled": False, "generation": 0, "consentedAt": None})
                    recipient.setdefault("toneObservation", None)
                    recipient.setdefault("transcriptSharing", {"enabled": False, "generation": 0, "consentedAt": None})
                    recipient.setdefault("alertSharing", {"enabled": False, "generation": 0, "consentedAt": None})
                    recipient.setdefault("structuredContext", [])
                    recipient.setdefault("conversationContinuity", None)
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
        recipient.setdefault("toneContinuity", {"enabled": False, "generation": 0, "consentedAt": None})
        recipient.setdefault("transcriptSharing", {"enabled": False, "generation": 0, "consentedAt": None})
        recipient.setdefault("alertSharing", {"enabled": False, "generation": 0, "consentedAt": None})
        memory = FollowupState.model_validate(recipient["memory"])
        expire(memory, now())
        active = recipient.get("activeCall")
        def public_call(call):
            result = {key: value for key, value in call.items()
                      if key not in {"transcript", "summary", "summaryStartedAt",
                                     "summaryEmailDestinationGeneration"}}
            if "alert" in result:
                result["alert"] = {key: value for key, value in result["alert"].items()
                                   if key != "destinationGeneration"}
            stale_pending = (call.get("summaryStatus") == "pending" and call.get("summaryStartedAt")
                             and call["summaryStartedAt"] < (now() - timedelta(seconds=60)).isoformat())
            result["canGenerateLegacySummary"] = bool(
                recipient["transcriptSharing"]["enabled"]
                and call.get("transcriptStatus") == "available"
                and isinstance(call.get("transcript"), list)
                and (call.get("summaryStatus") not in {"available", "pending"} or stale_pending)
            )
            if (stale_pending or (result.get("summaryStatus") == "pending" and result.get("endedAt")
                    and result["endedAt"] < (now() - timedelta(seconds=60)).isoformat())):
                result["summaryStatus"] = "unavailable"
            return result
        return {key: recipient[key] for key in (
            "recipientId", "label", "relationship", "timeZone", "revision", "background", "structuredContext", "voice",
        )} | {
            "calls": [public_call(call) for call in recipient["calls"]],
            "language": recipient.get("language", "auto"),
            "legacy": recipient.get("legacy", False),
            "memoryEnabled": memory.consent and not memory.privacy_hold,
            "memoryCount": len(memory.concerns) if memory.consent and not memory.privacy_hold else 0,
            "memoryCooldownHours": settings.FOLLOWUP_COOLDOWN_HOURS,
            "busy": bool(active and active["leaseUntil"] > now().isoformat()),
            "wellbeingSharingEnabled": bool(recipient["wellbeingSharing"]["enabled"]),
            "toneContinuityEnabled": bool(recipient["toneContinuity"]["enabled"]),
            "transcriptSharingEnabled": bool(recipient["transcriptSharing"]["enabled"]),
            "alertSharingEnabled": bool(recipient["alertSharing"]["enabled"]),
            "continuityAvailable": bool(
                recipient.get("conversationContinuity")
                and recipient["conversationContinuity"].get("expiresAt", "") > now().isoformat()
            ),
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
        destination = self._alert_destination(state)
        return {key: state[key] for key in ("familyId", "childId", "expiresAt", "schemaVersion")} | {
            "syntheticOnly": True,
            "childName": state.get("childName"),
            "childGender": state.get("childGender"),
            "childGenderRevision": state.get("childGenderRevision", 0),
            "storageMode": settings.HUGBACK_DEMO_STORE,
            "alertEmailSelected": bool(destination),
            "alertEmailHint": self._alert_email_hint(destination),
            "alertEmailConfigured": self._alert_destination_ready(state),
            "recipients": [self.public_recipient(recipient) for recipient in state["recipients"]],
        }

    @staticmethod
    def _alert_destination(state):
        value = state.get("alertEmail", "")
        return value if valid_destination(value) else None

    @classmethod
    def _alert_destination_ready(cls, state):
        return bool(alert_email_configured() and cls._alert_destination(state))

    @classmethod
    def _alert_destination_token(cls, state):
        destination = cls._alert_destination(state)
        return hashlib.sha256(destination.casefold().encode()).hexdigest() if destination else None

    @staticmethod
    def _alert_email_hint(address):
        if not address or "@" not in address:
            return None
        local, domain = address.split("@", 1)
        return f"{local[:1]}***@{domain}"

    def set_alert_destination(self, uid: str, request: SetAlertDestination):
        """Save one owner-scoped destination in the backend-only family record."""
        def action(state):
            if state["familyId"] != request.familyId:
                raise DemoError("Select your current demo family before setting its test email.", 404)
            if request.email != state.get("alertEmail"):
                state["alertEmail"] = request.email
                state["alertEmailGeneration"] = state.get("alertEmailGeneration", 0) + 1
                for recipient in state["recipients"]:
                    for call in recipient["calls"]:
                        if call.get("alert", {}).get("status") == "pending":
                            call["alert"]["status"] = "not_configured"
                        if call.get("summaryEmailStatus") == "pending":
                            call["summaryEmailStatus"] = "not_configured"
            state.pop("alertEmailHash", None)  # discard the older allowlist marker
            return self.public(state)
        return self._run(action, uid=uid)

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
            "revision": 0, "background": [], "structuredContext": [],
            "conversationContinuity": None, "backgroundCallCount": 0,
            "calls": [], "activeCall": None,
            "memory": memory.model_dump(mode="json"), "voice": {"mode": "standard", "profileId": None},
            "wellbeingSharing": {
                "enabled": request.enableWellbeingSharing,
                "generation": 1 if request.enableWellbeingSharing else 0,
                "consentedAt": now().isoformat() if request.enableWellbeingSharing else None,
            },
            "wellbeingSignals": [],
            "toneContinuity": {
                "enabled": request.enableToneContinuity,
                "generation": 1 if request.enableToneContinuity else 0,
                "consentedAt": now().isoformat() if request.enableToneContinuity else None,
            },
            "toneObservation": None,
            "transcriptSharing": {
                "enabled": request.enableTranscriptSharing,
                "generation": 1 if request.enableTranscriptSharing else 0,
                "consentedAt": now().isoformat() if request.enableTranscriptSharing else None,
            },
            "alertSharing": {
                "enabled": request.enableAlertSharing,
                "generation": 1 if request.enableAlertSharing else 0,
                "consentedAt": now().isoformat() if request.enableAlertSharing else None,
            },
        }

    def create(self, uid: str, request: CreateFamily):
        def action(state):
            if not state:
                state.update({
                    "schemaVersion": 2, "familyId": f"demo-family-{uuid.uuid4().hex}",
                    "childId": f"demo-child-{uuid.uuid4().hex}",
                    "childName": request.childName,
                    "childGender": request.childGender, "childGenderRevision": 0,
                    "expiresAt": (now() + timedelta(days=7)).isoformat(),
                    "recipients": [self.new_recipient(request)],
                })
            return self.public(state)
        return self._run(action, uid=uid, create=True)

    def set_child_gender(self, uid, request: SetChildGender):
        def action(state):
            if state["familyId"] != request.familyId:
                raise DemoError("Choose your own demo family.", 404)
            if state.get("childGenderRevision", 0) != request.revision:
                raise DemoError("Child details changed in another tab. Refresh before continuing.")
            next_name = request.childName if request.childName is not None else state.get("childName")
            if state.get("childGender") == request.childGender and state.get("childName") == next_name:
                return self.public(state)
            state["childName"] = next_name
            state["childGender"] = request.childGender
            state["childGenderRevision"] = request.revision + 1
            return self.public(state)
        return self._run(action, uid=uid)

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

    def review(self, uid, request: ReviewBackground, structured_context=None):
        if structured_context is None:
            from app.demo.context import deterministic_context
            structured_context = deterministic_context(request.excerpts, request.childSender)
        def action(state):
            recipient = self._editable(state, request.recipientId, request.revision)
            recipient["background"] = [item.model_dump() | {
                "role": "child" if item.sender == request.childSender else "parent",
                "source": request.source, "reviewedAt": now().isoformat(),
            } for item in request.excerpts]
            recipient["structuredContext"] = list(structured_context or [])[:12]
            recipient["backgroundCallCount"] = 0
            recipient["revision"] += 1
            return self.public(state)
        return self._run(action, uid=uid)


    def clear(self, uid, recipient_id, revision):
        def action(state):
            recipient = self._editable(state, recipient_id, revision)
            recipient["background"] = []
            recipient["structuredContext"] = []
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

    def set_tone_continuity(self, uid, request: SetToneContinuity):
        def action(state):
            recipient = self._editable(state, request.recipientId, request.revision)
            continuity = recipient["toneContinuity"]
            if continuity["enabled"] == request.enabled:
                return self.public(state)
            continuity.update(
                enabled=request.enabled,
                generation=continuity["generation"] + 1,
                consentedAt=now().isoformat() if request.enabled else None,
            )
            recipient["toneObservation"] = None
            recipient["revision"] += 1
            return self.public(state)
        return self._run(action, uid=uid)

    def set_transcript_sharing(self, uid, request: SetTranscriptSharing):
        def action(state):
            recipient = self._editable(state, request.recipientId, request.revision)
            sharing = recipient["transcriptSharing"]
            if sharing["enabled"] == request.enabled:
                return self.public(state)
            sharing.update(enabled=request.enabled, generation=sharing["generation"] + 1,
                           consentedAt=now().isoformat() if request.enabled else None)
            if not request.enabled:
                recipient["conversationContinuity"] = None
                alert_sharing = recipient["alertSharing"]
                alert_sharing.update(enabled=False, generation=alert_sharing["generation"] + 1,
                                     consentedAt=None)
                for call in recipient["calls"]:
                    call.pop("transcript", None)
                    call.pop("summary", None)
                    call.pop("summaryStartedAt", None)
                    call.pop("alert", None)
                    if call.get("transcriptStatus") == "available":
                        call["transcriptStatus"] = "revoked"
                    if call.get("summaryStatus") in {"available", "pending"}:
                        call["summaryStatus"] = "revoked"
            recipient["revision"] += 1
            return self.public(state)
        return self._run(action, uid=uid)

    def revoke_transcript_sharing(self, parent, expected_generation):
        def action(state):
            recipient = self._recipient(state, parent)
            sharing = recipient["transcriptSharing"]
            if sharing["generation"] != expected_generation:
                return False
            sharing.update(enabled=False, generation=sharing["generation"] + 1, consentedAt=None)
            recipient["conversationContinuity"] = None
            alert_sharing = recipient["alertSharing"]
            alert_sharing.update(enabled=False, generation=alert_sharing["generation"] + 1,
                                 consentedAt=None)
            for call in recipient["calls"]:
                call.pop("transcript", None)
                call.pop("summary", None)
                call.pop("summaryStartedAt", None)
                call.pop("alert", None)
                if call.get("transcriptStatus") in {"available", "pending"}:
                    call["transcriptStatus"] = "revoked"
                if call.get("summaryStatus") in {"available", "pending"}:
                    call["summaryStatus"] = "revoked"
            recipient["revision"] += 1
            return True
        return self._run(action, parent=parent)

    def set_alert_sharing(self, uid, request: SetAlertSharing):
        def action(state):
            recipient = self._editable(state, request.recipientId, request.revision)
            if request.enabled and not recipient["transcriptSharing"]["enabled"]:
                raise DemoError("Enable complete test-call history before email alerts.")
            sharing = recipient["alertSharing"]
            if sharing["enabled"] == request.enabled:
                return self.public(state)
            sharing.update(enabled=request.enabled, generation=sharing["generation"] + 1,
                           consentedAt=now().isoformat() if request.enabled else None)
            if not request.enabled:
                for call in recipient["calls"]:
                    call.pop("alert", None)
            recipient["revision"] += 1
            return self.public(state)
        return self._run(action, uid=uid)

    def revoke_alert_sharing(self, parent, expected_generation):
        def action(state):
            recipient = self._recipient(state, parent)
            sharing = recipient["alertSharing"]
            if sharing["generation"] != expected_generation:
                return False
            sharing.update(enabled=False, generation=sharing["generation"] + 1, consentedAt=None)
            for call in recipient["calls"]:
                call.pop("alert", None)
            recipient["revision"] += 1
            return True
        return self._run(action, parent=parent)

    def reserve_alert(self, parent, session_id, expected_generation, category, *, email_configured):
        if category not in {"fever", "bereavement"}:
            raise DemoError("Unsupported call alert category")
        def action(state):
            recipient = self._recipient(state, parent)
            sharing = recipient["alertSharing"]
            active = recipient.get("activeCall")
            if not (sharing["enabled"] and sharing["generation"] == expected_generation
                    and recipient["transcriptSharing"]["enabled"]
                    and active and active["sessionId"] == session_id):
                return False
            call = next((item for item in recipient["calls"] if item["sessionId"] == session_id), None)
            if call is None or call.get("transcriptStatus") != "available" or "alert" in call:
                return False
            cutoff = now() - timedelta(hours=24)
            recent = any(
                other.get("alert", {}).get("category") == category
                and other["alert"].get("status") in {"pending", "sending", "sent"}
                and datetime.fromisoformat(other["alert"]["observedAt"]) > cutoff
                for other in recipient["calls"] if other is not call and other.get("alert")
            )
            call["alert"] = {
                "category": category, "observedAt": now().isoformat(),
                "status": "suppressed" if recent else "pending" if email_configured and self._alert_destination_ready(state) else "not_configured",
                "destinationGeneration": self._alert_destination_token(state),
            }
            return call["alert"]["status"] == "pending"
        return self._run(action, parent=parent)

    def claim_alert_send(self, parent, session_id, expected_generation):
        def action(state):
            recipient = self._recipient(state, parent)
            sharing = recipient["alertSharing"]
            if not (sharing["enabled"] and sharing["generation"] == expected_generation
                    and recipient["transcriptSharing"]["enabled"]
                    and self._alert_destination_ready(state)):
                return None
            call = next((item for item in recipient["calls"] if item["sessionId"] == session_id), None)
            if not call or call.get("alert", {}).get("status") != "pending":
                return None
            if call["alert"].get("destinationGeneration") != self._alert_destination_token(state):
                call["alert"]["status"] = "not_configured"
                return None
            call["alert"]["status"] = "sending"
            return {"label": recipient["label"], "startedAt": call["startedAt"],
                    "email": self._alert_destination(state), "childName": state.get("childName"),
                    "timeZone": recipient.get("timeZone", "UTC")}
        return self._run(action, parent=parent)

    def finish_alert_send(self, parent, session_id, expected_generation, *, delivered):
        def action(state):
            recipient = self._recipient(state, parent)
            sharing = recipient["alertSharing"]
            if sharing["generation"] != expected_generation:
                return False
            call = next((item for item in recipient["calls"] if item["sessionId"] == session_id), None)
            if not call or call.get("alert", {}).get("status") != "sending":
                return False
            call["alert"]["status"] = "sent" if delivered else "failed"
            return True
        return self._run(action, parent=parent)

    def record_transcript(self, parent, session_id, expected_generation, turns):
        """Validate bounded call text for summary/alert processing; retain no turns."""
        def action(state):
            recipient = self._recipient(state, parent)
            sharing = recipient["transcriptSharing"]
            active = recipient.get("activeCall")
            if not (sharing["enabled"] and sharing["generation"] == expected_generation
                    and active and active["sessionId"] == session_id):
                return False
            call = next((item for item in recipient["calls"] if item["sessionId"] == session_id), None)
            if call is None or call.get("transcriptStatus") != "pending":
                return False
            if not turns:
                call["transcriptStatus"] = "unavailable"
                call["summaryFailureCode"] = "missing_text"
                return False
            if (len(turns) > MAX_TRANSCRIPT_TURNS
                    or sum(len(turn.text) for turn in turns) > MAX_TRANSCRIPT_CHARS):
                call["transcriptStatus"] = "unavailable"
                call["summaryFailureCode"] = "input_too_long"
                return False
            call["transcriptStatus"] = "available"
            return True
        return self._run(action, parent=parent)

    def record_call_summary(self, parent, session_id, expected_generation, summary, *, failure_code="model_or_content"):
        """Commit only bounded model text while current recipient consent matches."""
        def action(state):
            recipient = self._recipient(state, parent)
            sharing = recipient["transcriptSharing"]
            if not (sharing["enabled"] and sharing["generation"] == expected_generation):
                return False
            call = next((item for item in recipient["calls"] if item["sessionId"] == session_id), None)
            if not call or call.get("summaryStatus") != "pending" or call.get("transcriptStatus") != "available":
                return False
            if not isinstance(summary, str) or not 20 <= len(summary) <= 600:
                call["summaryStatus"] = "unavailable"
                call["summaryFailureCode"] = (failure_code if failure_code in {
                    "missing_text", "input_too_long", "model_or_content", "timeout",
                    "provider_access", "model_unavailable", "rate_limited",
                    "provider_unavailable", "provider_request_rejected",
                    "network_unavailable", "invalid_output", "processing_failed",
                } else "model_or_content")
                return False
            call["summary"] = summary
            call["summaryStatus"] = "available"
            call.pop("summaryFailureCode", None)
            call["summaryEmailStatus"] = (
                "pending" if self._alert_destination_ready(state) else "not_configured"
            )
            call["summaryEmailDestinationGeneration"] = self._alert_destination_token(state)
            recipient["conversationContinuity"] = {
                "sourceSessionId": session_id,
                "summary": summary,
                "createdAt": now().isoformat(),
                "expiresAt": (now() + timedelta(days=30)).isoformat(),
            }
            return True
        return self._run(action, parent=parent)

    def claim_summary_email(self, parent, session_id, expected_generation):
        def action(state):
            recipient = self._recipient(state, parent)
            sharing = recipient["transcriptSharing"]
            if not (sharing["enabled"] and sharing["generation"] == expected_generation
                    and self._alert_destination_ready(state)):
                return None
            call = next((item for item in recipient["calls"] if item["sessionId"] == session_id), None)
            if (not call or call.get("summaryStatus") != "available"
                    or call.get("summaryEmailStatus") != "pending"):
                return None
            if call.get("summaryEmailDestinationGeneration") != self._alert_destination_token(state):
                call["summaryEmailStatus"] = "not_configured"
                return None
            call["summaryEmailStatus"] = "sending"
            return {
                "label": recipient["label"], "startedAt": call["startedAt"],
                "email": self._alert_destination(state), "childName": state.get("childName"),
                "summary": call["summary"], "timeZone": recipient.get("timeZone", "UTC"),
            }
        return self._run(action, parent=parent)

    def finish_summary_email(self, parent, session_id, expected_generation, *, delivered):
        def action(state):
            recipient = self._recipient(state, parent)
            if recipient["transcriptSharing"]["generation"] != expected_generation:
                return False
            call = next((item for item in recipient["calls"] if item["sessionId"] == session_id), None)
            if not call or call.get("summaryEmailStatus") != "sending":
                return False
            call["summaryEmailStatus"] = "sent" if delivered else "failed"
            return True
        return self._run(action, parent=parent)

    def summary_eligible(self, parent, session_id, expected_generation):
        def action(state):
            recipient = self._recipient(state, parent)
            sharing = recipient["transcriptSharing"]
            call = next((item for item in recipient["calls"] if item["sessionId"] == session_id), None)
            return bool(sharing["enabled"] and sharing["generation"] == expected_generation
                        and call and call.get("summaryStatus") == "pending"
                        and call.get("transcriptStatus") == "available")
        return self._run(action, parent=parent)

    def claim_legacy_summary(self, uid, recipient_id, revision, session_id):
        """Claim one explicit paid conversion; return old turns only inside backend."""
        def action(state):
            recipient = self._recipient(state, recipient_id)
            if recipient["revision"] != revision:
                raise DemoError("Recipient settings changed. Refresh before summarizing.")
            sharing = recipient["transcriptSharing"]
            if not sharing["enabled"]:
                raise DemoError("Call sharing is off for this recipient.", 403)
            call = next((item for item in recipient["calls"] if item["sessionId"] == session_id), None)
            if not call or call.get("transcriptStatus") != "available" or not isinstance(call.get("transcript"), list):
                raise DemoError("No older saved call can be summarized.", 404)
            stale_pending = (call.get("summaryStatus") == "pending" and call.get("summaryStartedAt")
                             and call["summaryStartedAt"] < (now() - timedelta(seconds=60)).isoformat())
            if call.get("summaryStatus") == "available" or (call.get("summaryStatus") == "pending" and not stale_pending):
                raise DemoError("A summary already exists or is being prepared.")
            call["summaryStatus"] = "pending"
            call["summaryStartedAt"] = now().isoformat()
            return {"turns": call["transcript"], "generation": sharing["generation"]}
        return self._run(action, uid=uid)

    def finish_legacy_summary(self, uid, recipient_id, session_id, generation, summary):
        def action(state):
            recipient = self._recipient(state, recipient_id)
            sharing = recipient["transcriptSharing"]
            if not sharing["enabled"] or sharing["generation"] != generation:
                return False
            call = next((item for item in recipient["calls"] if item["sessionId"] == session_id), None)
            if not call or call.get("summaryStatus") != "pending" or "transcript" not in call:
                return False
            if not isinstance(summary, str) or not 20 <= len(summary) <= 600:
                call["summaryStatus"] = "unavailable"
                call.pop("summaryStartedAt", None)
                return False
            call["summary"] = summary
            call["summaryStatus"] = "available"
            call.pop("summaryStartedAt", None)
            call.pop("transcript", None)
            recipient["conversationContinuity"] = {
                "sourceSessionId": session_id, "summary": summary,
                "createdAt": now().isoformat(),
                "expiresAt": (now() + timedelta(days=30)).isoformat(),
            }
            return True
        return self._run(action, uid=uid)

    def get_call_summary(self, uid, recipient_id, session_id):
        def action(state):
            recipient = self._recipient(state, recipient_id)
            if not recipient["transcriptSharing"]["enabled"]:
                raise DemoError("Call sharing is off for this recipient.", 403)
            call = next((item for item in recipient["calls"] if item["sessionId"] == session_id), None)
            if not call or call.get("summaryStatus") != "available":
                raise DemoError("No saved summary for this test call.", 404)
            return {"sessionId": session_id, "startedAt": call["startedAt"],
                    "endedAt": call.get("endedAt"), "summary": call["summary"],
                    "syntheticOnly": True}
        return self._run(action, uid=uid)


    def start_call(self, uid, session_id, recipient_id, revision, voice_profile_id=None):
        if not isinstance(recipient_id, str) or type(revision) is not int or revision < 0:
            raise DemoError("Explicit recipient selection and current setup revision are required.", 400)
        def action(state):
            recipient = self._editable(state, recipient_id, revision)
            selected_voice = recipient["voice"]
            if voice_profile_id != selected_voice["profileId"]:
                raise DemoError("This recipient's voice selection changed. Refresh before calling.")
            prior_tone = recipient.get("toneObservation") if recipient["toneContinuity"]["enabled"] else None
            # A prior cue is available for only the next attempted call. A new
            # qualifying cue from that call may replace it after completion.
            recipient["toneObservation"] = None
            recipient["activeCall"] = {
                "sessionId": session_id, "leaseUntil": (now() + timedelta(minutes=12)).isoformat(),
            }
            if recipient["background"]:
                recipient["backgroundCallCount"] = recipient.get("backgroundCallCount", 0) + 1
            recipient["calls"] = (recipient["calls"] + [{
                "sessionId": session_id, "startedAt": now().isoformat(), "status": "connecting",
                "transcriptStatus": "pending" if recipient["transcriptSharing"]["enabled"] else "not_enabled",
                "summaryStatus": "pending" if recipient["transcriptSharing"]["enabled"] else "not_enabled",
            }])[-20:]
            # Preserve the broker/coordinator's internal parent-scoped contract.
            return {**recipient, "toneObservation": prior_tone,
                    "parentId": recipient_id, "familyId": state["familyId"], "childId": state["childId"],
                    "childGender": state.get("childGender")}
        return self._run(action, uid=uid)


    def call_status(self, parent, session_id, status, *, release=False, quality_pending=False,
                    memory_error=None, planner_status=None):
        if memory_error is not None and memory_error not in MEMORY_ERROR_CODES:
            raise DemoError("Invalid memory failure category")
        if planner_status is not None and (
            status != "active" or planner_status not in ("ready", "fallback")
        ):
            raise DemoError("Invalid activation planner status")
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
                    if planner_status is not None:
                        call.setdefault("workflow", {})["planner"] = planner_status
                    if status == "memory_failed":
                        call["memoryErrorCode"] = memory_error or "processing_failed"
                    else:
                        call.pop("memoryErrorCode", None)
                    if release:
                        if call.get("transcriptStatus") == "pending":
                            call["transcriptStatus"] = "unavailable"
                        if (call.get("summaryStatus") == "pending"
                                and (call.get("transcriptStatus") != "available" or status == "failed")):
                            call["summaryStatus"] = "unavailable"
                            call.setdefault("summaryFailureCode", "processing_unavailable")
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


    def record_tone_observation(self, parent, session_id, expected_generation,
                                draft: WellbeingSignalDraft, *, retention_hours=72):
        """Keep one short recipient-scoped cue; never audio, a voiceprint, or identity proof."""
        if (draft.confidence != "high" or "vocal_cues" not in draft.basis
                or draft.category not in {"upbeat", "calm", "lower_energy", "tense"}):
            return False
        def action(state):
            recipient = self._recipient(state, parent)
            continuity = recipient["toneContinuity"]
            active = recipient.get("activeCall")
            if (not continuity["enabled"] or continuity["generation"] != expected_generation
                    or not active or active["sessionId"] != session_id):
                return False
            created = now()
            recipient["toneObservation"] = {
                "category": draft.category,
                "confidence": "high",
                "basis": "vocal_cues",
                "observedAt": created.isoformat(),
                "expiresAt": (created + timedelta(hours=retention_hours)).isoformat(),
                "policyVersion": "demo-tone-v1",
            }
            return True
        return self._run(action, parent=parent)


    def revoke_tone_continuity(self, parent, expected_generation):
        def action(state):
            recipient = self._recipient(state, parent)
            continuity = recipient["toneContinuity"]
            if not continuity["enabled"] or continuity["generation"] != expected_generation:
                return False
            continuity.update(enabled=False, generation=continuity["generation"] + 1,
                              consentedAt=None)
            recipient["toneObservation"] = None
            recipient["revision"] += 1
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

    def inspect_tone(self, uid, recipient_id):
        """Operator-only synthetic cue status; no words, audio or browser route."""
        def read(state):
            recipient = self._recipient(state, recipient_id)
            note = recipient.get("toneObservation") or {}
            expires_at = note.get("expiresAt")
            active = False
            if recipient["toneContinuity"]["enabled"] and expires_at:
                try:
                    expiry = datetime.fromisoformat(expires_at)
                    active = bool(expiry.tzinfo and expiry > now())
                except (TypeError, ValueError):
                    pass
            return {
                "recipientId": recipient_id,
                "enabled": bool(recipient["toneContinuity"]["enabled"]),
                "activeNote": active,
                "category": note.get("category") if active else None,
                "confidence": note.get("confidence") if active else None,
                "observedAt": note.get("observedAt") if active else None,
                "expiresAt": expires_at if active else None,
            }
        return self._run(read, uid=uid)

    async def quality_eligible(self, parent, revision, generation):
        def check(state):
            recipient = self._recipient(state, parent)
            return (recipient["revision"] == revision and recipient["memory"]["generation"] == generation
                    and not recipient["memory"].get("privacy_hold"))
        return await asyncio.to_thread(self._run, check, parent=parent)
