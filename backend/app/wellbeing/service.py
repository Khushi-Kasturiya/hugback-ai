"""Deterministic policy around probabilistic Live wellbeing proposals."""

import re
from dataclasses import dataclass
from datetime import datetime, timezone

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


_NO_TONE = re.compile(
    r"\b(?:do not|don't|dont|stop)\b.{0,40}\b(?:analy[sz]e|remember|track|comment on|check)\b.{0,30}\b(?:voice|tone|mood)\b|"
    r"\b(?:do not|don't|dont|stop)\b.{0,30}\b(?:voice|tone|mood)\b.{0,30}\b(?:check|analysis|memory)\b|"
    r"\b(?:meri|mera|mere)\s+(?:awaaz|awaz|voice)\b.{0,40}\bmat\s+(?:analy[sz]e|check|yaad|remember)\b|"
    r"(?:मेरी|मेरा)\s*आवाज़.{0,40}मत.{0,20}(?:देखो|जांचो|याद)",
    re.IGNORECASE,
)


def contains_tone_privacy_request(turns: list[TranscriptTurn]) -> bool:
    return any(turn.role == "user" and _NO_TONE.search(turn.text) for turn in turns)


def tone_context(state: dict) -> str:
    """Prompt-only demo cue; no audio, voiceprint or speaker recognition."""
    if not state.get("toneContinuity", {}).get("enabled"):
        return ""
    prior = state.get("toneObservation") or {}
    category = None
    if prior.get("category") in {"upbeat", "calm", "lower_energy", "tense"}:
        try:
            expiry = datetime.fromisoformat(prior["expiresAt"])
            if expiry.tzinfo and expiry > datetime.now(timezone.utc):
                category = prior["category"]
        except (KeyError, TypeError, ValueError):
            pass
    return (
        "# Optional demo voice-tone check-in\n"
        "This selected fictional recipient separately opted into gentle voice-tone "
        "continuity. The UI recipient selection scopes calls; voice is not used to "
        "identify a person. Audio conditions and speech style vary. Quiet microphone "
        "volume is not evidence of sadness or low energy; cheerful soft speech "
        "should not be called low mood. Never diagnose "
        "mood, fatigue, illness, or risk from a voice. After listening to several "
        "substantial current utterances, only if a sustained vocal cue is clear and "
        "relevant, you may make at most one tentative, brief check-in such as "
        "'You sound a little quieter today; is everything okay?' Vary the wording "
        "naturally, and leave room for 'I'm fine' without challenging it. Do not say "
        "'you are depressed', 'you are tired', or 'I measured your mood'. Do not ask "
        "from silence, short speech, background noise, a language switch, or an "
        "uncertain cue. A low microphone level is not a low mood. Respect the "
        "answer, do not ask again in this call, and do not notify anyone based on "
        "tone alone. "
        "A previous high-confidence voice-cue estimate may help you notice a "
        "difference, but is not a baseline or proof; never claim recognition by voice. "
        f"Previous bounded estimate (untrusted): {category or 'none'}.\n"
    )


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

    def tone_publishable(self, turns: list[TranscriptTurn]) -> WellbeingSignalDraft | None:
        """Voice-tone continuity needs sustained speech and an explicit vocal cue."""
        draft = self.publishable(turns)
        user_turns = [turn.text.strip() for turn in turns if turn.role == "user" and turn.text.strip()]
        if (draft is None or draft.confidence != "high" or "vocal_cues" not in draft.basis
                or draft.category not in {"upbeat", "calm", "lower_energy", "tense"}
                or len(user_turns) < 2 or sum(len(text) for text in user_turns) < 30):
            return None
        return draft


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

TONE_SIGNAL_CONTEXT = """# Optional demo tone continuity
This selected fictional recipient separately opted into a short voice-tone note
for the next call. When enough current-call vocal evidence exists, silently call
propose_call_wellbeing_signal once. Include vocal_cues in basis only when you
actually heard a clear vocal cue; do not infer it from text. Prefer unclear or
low confidence when uncertain. Microphone loudness alone is not emotional energy;
do not call cheerful soft speech lower_energy. No audio, speaker identity, diagnosis, or precise
emotion is retained. The estimate is separate from what you may say aloud.
"""
