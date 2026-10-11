"""Deterministic policy around probabilistic Live wellbeing proposals."""

import re
from dataclasses import dataclass

from pydantic import ValidationError

from app.memory.models import TranscriptTurn
from app.wellbeing.models import WellbeingSignalDraft


_DO_NOT_SHARE = re.compile(
    r"\b(do not|don't|dont|stop)\s+(?:share|tell|send)\b|"
    r"\b(?:share|tell)\s+(?:nothing|none of this)\b|"
    r"\b(?:meri|mera|mere)\b.{0,60}\bmat\s+(?:batana|bhejna|share)\b|"
    r"मत.{0,40}(?:बताना|भेजना|साझा)",
    re.IGNORECASE,
)


def contains_signal_privacy_request(turns: list[TranscriptTurn]) -> bool:
    return any(turn.role == "user" and _DO_NOT_SHARE.search(turn.text) for turn in turns)


@dataclass
class SignalCollector:
    """Keeps at most one validated draft in memory for the current call."""

    enabled: bool
    draft: WellbeingSignalDraft | None = None

    def propose(self, args) -> dict:
        if not self.enabled:
            return {"accepted": False, "reason": "Wellbeing sharing is not enabled."}
        try:
            candidate = WellbeingSignalDraft.model_validate(args if isinstance(args, dict) else {})
        except ValidationError:
            return {"accepted": False, "reason": "Signal did not match the bounded schema."}
        # Low-confidence/unclear results are useful abstentions, not child-facing conclusions.
        self.draft = candidate
        return {"accepted": True, "guidance": "Continue the conversation naturally; do not announce the estimate."}

    def publishable(self, turns: list[TranscriptTurn]) -> WellbeingSignalDraft | None:
        if (
            not self.enabled
            or self.draft is None
            or self.draft.category == "unclear"
            or self.draft.confidence == "low"
            or not any(turn.role == "user" and turn.text.strip() for turn in turns)
            or contains_signal_privacy_request(turns)
        ):
            return None
        return self.draft


SIGNAL_CONTEXT = """# Optional wellbeing sharing
This recipient separately consented in the local synthetic demo to share one short,
AI-estimated conversation signal with the child. This is not diagnosis, monitoring,
or proof of an emotion. When there is enough evidence, silently call
propose_call_wellbeing_signal with exactly one bounded estimate. Prefer unclear and
low confidence when evidence is weak. Base the estimate only on this call's parent's
own words, conversational content, and vocal cues. Never infer depression, illness,
cognitive state, danger, or a need for emergency action. Do not mention the hidden
estimate to the caller and do not alter the caring conversation to collect one.
"""
