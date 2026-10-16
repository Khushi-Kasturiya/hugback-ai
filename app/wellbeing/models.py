"""Bounded schemas for AI-estimated conversation signals."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SignalCategory = Literal["upbeat", "calm", "neutral", "lower_energy", "tense", "unclear"]
SignalConfidence = Literal["low", "medium", "high"]
SignalBasis = Literal["explicit_self_report", "conversation_content", "vocal_cues"]


class WellbeingSignalDraft(BaseModel):
    """Untrusted Live-model proposal. It never carries identity or authority."""

    model_config = ConfigDict(extra="forbid")
    category: SignalCategory
    confidence: SignalConfidence
    basis: list[SignalBasis] = Field(min_length=1, max_length=3)


DISPLAY_TEXT = {
    "upbeat": "Sounded upbeat and engaged during this check-in.",
    "calm": "The conversation sounded calm and settled.",
    "neutral": "The conversation sounded generally neutral.",
    "lower_energy": "Sounded lower-energy during this check-in.",
    "tense": "Sounded tense at points during this check-in.",
}


def display_text(category: SignalCategory) -> str:
    return DISPLAY_TEXT[category]
