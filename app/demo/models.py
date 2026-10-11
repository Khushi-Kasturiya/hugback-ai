"""Bounded demo inputs; recipient selectors require server-side membership checks."""

from datetime import datetime, timezone
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
    timeZone: str = Field(default="Asia/Kolkata", max_length=80)

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


class SetWellbeingSharing(RecipientTarget):
    enabled: bool
    simulateChildConsent: bool = False
    simulateParentConsent: bool = False

    @model_validator(mode="after")
    def explicit_consent(self):
        if self.enabled and not (self.simulateChildConsent and self.simulateParentConsent):
            raise ValueError("Enabling demo signal sharing requires both simulated consents")
        return self


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
    excerpts: list[Excerpt] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_mapping(self):
        if self.childSender == self.parentSender:
            raise ValueError("Map two different participants")
        if len({e.sourceIndex for e in self.excerpts}) != len(self.excerpts):
            raise ValueError("Duplicate source message")
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
