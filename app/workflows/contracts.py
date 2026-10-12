"""Bounded model proposals. Identity and consent never come from a model."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Language = Literal["auto", "en", "hi", "hi-en"]

class ConversationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    language: Language = "auto"
    opening: Literal["gentle", "neutral"] = "gentle"
    background_refs: list[int] = Field(default_factory=list, max_length=2)
    consider_followup: bool = False

class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    code: Literal["missing_ai_disclosure", "repeated_followup", "unsupported_memory",
                  "ignored_topic_change", "false_memory_action", "impersonation",
                  "language_mismatch"]
    severity: Literal["warning", "error"]
    source_turn: int = Field(ge=0)
    evidence: str = Field(min_length=1, max_length=200)

class CritiqueReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    findings: list[Finding] = Field(default_factory=list, max_length=8)
    uncertain: bool = False

class ToolOutcome(BaseModel):
    """Only safe result categories; no arguments, memory quotes, or owner IDs."""
    name: Literal["claim_followup", "control_followup"]
    succeeded: bool
