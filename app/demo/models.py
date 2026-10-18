"""Bounded demo inputs; recipient selectors require server-side membership checks."""

from datetime import datetime, timezone
import re
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DemoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    syntheticOnly: Literal[True]


class CreateRecipient(DemoInput):
    simulateChildConsent: Literal[True]
    simulateParentConsent: Literal[True]
    label: str = Field(default="Parent", min_length=1, max_length=40)
    relationship: Literal["mother", "father", "grandmother", "grandfather", "other"] = "other"
    enableMemory: bool = False
    enableWellbeingSharing: bool = False
    enableToneContinuity: bool = False
    simulateToneConsent: bool = False
    enableTranscriptSharing: bool = False
    enableAlertSharing: bool = False
    timeZone: str = Field(default="Asia/Kolkata", max_length=80)
    language: Literal["auto", "en", "hi", "hi-en"] = "auto"

    @model_validator(mode="after")
    def alerts_need_history(self):
        if self.enableAlertSharing and not self.enableTranscriptSharing:
            raise ValueError("Demo email alerts require transcript sharing for Signals back")
        if self.enableToneContinuity and not self.simulateToneConsent:
            raise ValueError("Demo voice-tone continuity requires separate simulated consent")
        return self

    @field_validator("label")
    @classmethod
    def clean_label(cls, value):
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError("Use a short, readable recipient label")
        return value

    @field_validator("timeZone")
    @classmethod
    def timezone_exists(cls, value):
        try:
            ZoneInfo(value)
        except (ValueError, KeyError):
            raise ValueError("Use an IANA timezone")
        return value


class CreateFamily(CreateRecipient):
    """Create the family and its first explicitly configured recipient."""
    childName: str | None = Field(default=None, min_length=1, max_length=40)
    childGender: Literal["female", "male", "neutral"] | None = None

    @field_validator("childName")
    @classmethod
    def clean_child_name(cls, value):
        if value is None:
            return None
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError("Use a short, readable fictional child name")
        return value


class SetChildGender(DemoInput):
    familyId: str = Field(pattern=r"^demo-family-[a-f0-9]{32}$")
    revision: int = Field(ge=0, strict=True)
    childName: str | None = Field(default=None, min_length=1, max_length=40)
    childGender: Literal["female", "male", "neutral"]

    @field_validator("childName")
    @classmethod
    def clean_child_name(cls, value):
        if value is None:
            return None
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError("Use a short, readable fictional child name")
        return value


class RecipientTarget(DemoInput):
    recipientId: str = Field(pattern=r"^demo-parent-[a-f0-9]{32}$")
    revision: int = Field(ge=0, strict=True)


class SelectRecipientVoice(RecipientTarget):
    mode: Literal["standard", "child"]
    profileId: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")

    @model_validator(mode="after")
    def explicit_voice(self):
        if (self.mode == "child") != (self.profileId is not None):
            raise ValueError("Choose standard voice or a specific authorized child voice")
        return self


class SetMemory(RecipientTarget):
    enabled: bool
    simulateChildConsent: bool = False
    simulateParentConsent: bool = False

    @model_validator(mode="after")
    def explicit_consent(self):
        if self.enabled and not (self.simulateChildConsent and self.simulateParentConsent):
            raise ValueError("Enabling demo memory requires both simulated consents")
        return self


class SetWellbeingSharing(RecipientTarget):
    enabled: bool
    simulateChildConsent: bool = False
    simulateParentConsent: bool = False

    @model_validator(mode="after")
    def explicit_consent(self):
        if self.enabled and not (self.simulateChildConsent and self.simulateParentConsent):
            raise ValueError("Enabling demo signal sharing requires both simulated consents")
        return self


class SetToneContinuity(RecipientTarget):
    enabled: bool
    simulateChildConsent: bool = False
    simulateParentConsent: bool = False

    @model_validator(mode="after")
    def explicit_consent(self):
        if self.enabled and not (self.simulateChildConsent and self.simulateParentConsent):
            raise ValueError("Enabling demo voice-tone continuity requires both simulated consents")
        return self


class SetTranscriptSharing(RecipientTarget):
    enabled: bool
    simulateChildConsent: bool = False
    simulateParentConsent: bool = False

    @model_validator(mode="after")
    def explicit_consent(self):
        if self.enabled and not (self.simulateChildConsent and self.simulateParentConsent):
            raise ValueError("Enabling demo transcript history requires both simulated consents")
        return self


class SetAlertSharing(RecipientTarget):
    enabled: bool
    simulateChildConsent: bool = False
    simulateParentConsent: bool = False

    @model_validator(mode="after")
    def explicit_consent(self):
        if self.enabled and not (self.simulateChildConsent and self.simulateParentConsent):
            raise ValueError("Enabling demo call alerts requires both simulated consents")
        return self


class SetAlertDestination(DemoInput):
    """Select or clear one local fictional-call test mailbox for this family."""
    familyId: str = Field(pattern=r"^demo-family-[a-f0-9]{32}$")
    email: str | None = Field(default=None, max_length=254)
    confirmTestRecipient: bool = False

    @field_validator("email")
    @classmethod
    def clean_email(cls, value):
        if value is None:
            return None
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", value):
            raise ValueError("Enter a valid test email address")
        return value

    @model_validator(mode="after")
    def require_confirmation(self):
        if self.email and not self.confirmTestRecipient:
            raise ValueError("Confirm the test recipient expects this email")
        return self


class GenerateLegacySummary(RecipientTarget):
    """Explicit operator request to convert an older synthetic saved call."""


class Excerpt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sourceIndex: int = Field(ge=0, lt=2000)
    sender: str = Field(min_length=1, max_length=100)
    timestamp: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=500)

    @field_validator("text", "sender")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Empty text is not allowed")
        return value


class ReviewBackground(RecipientTarget):
    simulateChildConsent: Literal[True]
    simulateParentConsent: Literal[True]
    source: Literal["whatsapp", "instagram"]
    childSender: str = Field(min_length=1, max_length=100)
    parentSender: str = Field(min_length=1, max_length=100)
    timeZone: str = Field(min_length=1, max_length=80)
    excerpts: list[Excerpt] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def validate_mapping(self):
        if self.childSender == self.parentSender:
            raise ValueError("Map two different participants")
        if len({e.sourceIndex for e in self.excerpts}) != len(self.excerpts):
            raise ValueError("Duplicate source message")
        child_count = sum(item.sender == self.childSender for item in self.excerpts)
        if child_count > 4 or (child_count and len(self.excerpts) - child_count > 20):
            raise ValueError("Keep at most four child style examples and twenty parent excerpts")
        try:
            zone = ZoneInfo(self.timeZone)
            for item in self.excerpts:
                if item.sender not in (self.childSender, self.parentSender):
                    raise ValueError("Unknown participant")
                timestamp = datetime.fromisoformat(item.timestamp)
                if timestamp.tzinfo is None:
                    first = timestamp.replace(tzinfo=zone, fold=0)
                    second = timestamp.replace(tzinfo=zone, fold=1)
                    if (first.utcoffset() != second.utcoffset() or
                        first.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != timestamp):
                        raise ValueError("Ambiguous local time; use an explicit offset")
                    timestamp = first
                item.timestamp = timestamp.isoformat()
        except (ValueError, KeyError):
            raise ValueError("Invalid participant, date or timezone")
        return self


class ClearBackground(RecipientTarget):
    pass
