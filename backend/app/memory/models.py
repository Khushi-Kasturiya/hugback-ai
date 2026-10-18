"""Data models shared by transcript storage and Memory Bank."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class TranscriptTurn(BaseModel):
    role: Literal["user", "model"]
    text: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    turn_index: int


class FamilyMember(BaseModel):
    name: str = Field(description="The person's name, only when explicitly shared.")
    relationship: str = Field(description="Their relationship to the user.")
    location: str = Field(description="Their location, only when relevant and shared.")
    notes: str = Field(description="Stable details useful for caring conversation.")


class OngoingConcern(BaseModel):
    topic: str = Field(description="A user-reported wellbeing or comfort concern.")
    status: Literal["open", "resolved", "unknown"] = Field(
        description=(
            "Resolve only when the user explicitly says it is resolved; otherwise "
            "keep it open or unknown."
        )
    )
    first_mentioned: str = Field(description="The first known mention date if available.")
    last_mentioned: str = Field(description="The latest known mention date if available.")
    notes: str = Field(description="User-reported context without inferred diagnosis.")


class CareProfile(BaseModel):
    """Schema uploaded to Memory Bank for low-latency profile retrieval."""

    preferred_name: str = Field(description="The name the user prefers Hugback to use.")
    preferred_languages: list[str] = Field(
        description="Languages and language-mixing preferences explicitly used or requested."
    )
    family_and_relationships: list[FamilyMember] = Field(
        description="Important people, their relationship to the user, and stable relevant details."
    )
    routines: list[str] = Field(description="Stable daily or weekly routines.")
    preferences: list[str] = Field(
        description="Hobbies, foods, activities, and other explicitly shared preferences."
    )
    ongoing_concerns: list[OngoingConcern] = Field(
        description=(
            "User-reported wellbeing or physical-comfort concerns. Never infer diagnoses. "
            "Include whether the concern is open or explicitly resolved."
        )
    )
    upcoming_events_and_followups: list[str] = Field(
        description="Upcoming events, appointments, visits, and natural follow-up topics."
    )
    communication_preferences: list[str] = Field(
        description="How the user prefers Hugback to speak, ask questions, or provide support."
    )


class ProcessMemoryRequest(BaseModel):
    user_id: str
    session_id: str
