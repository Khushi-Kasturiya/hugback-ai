"""Strict internal intake schemas; storing/reviewing does not grant consent."""
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_FILE_BYTES = 1024 * 1024
MAX_RECIPIENTS = 8
MAX_IMPORTS = 100


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    @field_validator("acknowledgeSetup", "acknowledgeUpload", check_fields=False, mode="before")
    @classmethod
    def literal_acknowledgement(cls, value):
        if value is not True:
            raise ValueError("Explicit acknowledgement must be true")
        return value


class RecipientInput(Input):
    requestId: str
    label: str = Field(min_length=1, max_length=40)
    relationship: Literal["mother", "father", "grandmother", "grandfather", "other"]
    phone: str = Field(pattern=r"^\+[1-9][0-9]{7,14}$")
    timeZone: str = Field(default="Asia/Kolkata", max_length=80)
    language: str = Field(default="Hindi", min_length=1, max_length=40)
    acknowledgeSetup: Literal[True]

    @field_validator("requestId")
    @classmethod
    def request_id(cls, value):
        return str(UUID(value))

    @field_validator("label", "language")
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("Use a readable label")
        return value

    @field_validator("timeZone")
    @classmethod
    def zone(cls, value):
        try:
            ZoneInfo(value)
        except (ValueError, KeyError):
            raise ValueError("Use an IANA timezone")
        return value


class ImportInput(Input):
    filename: str = Field(min_length=1, max_length=180)
    fileBase64: str = Field(min_length=1, max_length=1_398_104)
    source: Literal["whatsapp", "instagram"]
    dateOrder: Literal["DMY", "MDY"] = "DMY"
    timeZone: str = Field(default="Asia/Kolkata", max_length=80)
    childSender: str = Field(min_length=1, max_length=100)
    parentSender: str = Field(min_length=1, max_length=100)
    acknowledgeUpload: Literal[True]

    @field_validator("filename")
    @classmethod
    def safe_filename(cls, value):
        if any(ord(c) < 32 for c in value) or "/" in value or "\\" in value or value in (".", ".."):
            raise ValueError("Use a filename, not a path")
        return value

    _zone = field_validator("timeZone")(RecipientInput.zone.__func__)


class ReviewInput(Input):
    revision: int = Field(ge=0)
    sourceIndexes: list[int] = Field(min_length=1, max_length=8)

    @field_validator("sourceIndexes")
    @classmethod
    def indexes(cls, values):
        if len(set(values)) != len(values) or any(type(v) is not int or v < 0 or v >= 2000 for v in values):
            raise ValueError("Select distinct source messages")
        return values


class ImportMapping(Input):
    """Participant labels are declared attribution, not verified speaker identity."""
    source: Literal["whatsapp"] = "whatsapp"
    dateOrder: Literal["DMY", "MDY"] = "DMY"
    timeZone: str = Field(default="Asia/Kolkata", max_length=80)
    childSender: str = Field(min_length=1, max_length=100)
    parentSender: str = Field(min_length=1, max_length=100)
    acknowledgeUpload: Literal[True]

    _zone = field_validator("timeZone")(RecipientInput.zone.__func__)


class IntakeManifest(Input):
    # Operator-assigned stable subject UUID; never derived from a phone, voice,
    # filename, URL role selector or arbitrary Form-supplied owner field.
    ownerId: str
    recipient: RecipientInput
    mapping: ImportMapping

    _owner = field_validator("ownerId")(RecipientInput.request_id.__func__)
