"""Deterministic, conservative topic detection for a parent's own words."""

import re

from app.memory.models import TranscriptTurn

_FEVER = re.compile(
    r"\b(?:i\s+(?:have|got|feel|am feeling|think i have)|i'm\s+feeling)\b.{0,45}"
    r"\b(?:fever|feverish)\b|"
    r"\b(?:mujhe|mujhko|mere ko)\b.{0,35}\b(?:bukhar|bukhaar)\b|"
    r"मुझे.{0,35}बुखार",
    re.IGNORECASE,
)
_FEVER_NEGATION = re.compile(
    r"\b(?:no|not|don't have|do not have|never had)\s+(?:a\s+)?fever\b|"
    r"\bfever\s+(?:is\s+)?gone\b|बुखार\s+नहीं",
    re.IGNORECASE,
)
_BEREAVEMENT = re.compile(
    r"\bmy\s+(?:husband|wife|mother|father|mom|dad|son|daughter|brother|sister|friend|partner)"
    r"\b.{0,45}\b(?:died|passed away)\b|"
    r"\bsomeone\s+(?:close to me|in my family)\b.{0,45}\b(?:died|passed away)\b|"
    r"\b(?:mere|meri|mera)\s+(?:pati|patni|maa|papa|beta|beti|bhai|behen)\b.{0,45}"
    r"\b(?:guzar gaye|guzar gayi)\b",
    re.IGNORECASE,
)
_BEREAVEMENT_NEGATION = re.compile(r"\b(?:didn't|did not|hasn't|has not)\s+(?:die|pass away)\b", re.IGNORECASE)
_PRIVATE = re.compile(
    r"\b(?:do not|don't|dont|stop)\s+(?:email|notify|alert)\b|"
    r"\b(?:no|without)\s+(?:email|notification|alert)s?\b|"
    r"(?:मेल|ईमेल|सूचना).{0,25}मत",
    re.IGNORECASE,
)


def asks_not_to_alert(turns: list[TranscriptTurn]) -> bool:
    return any(turn.role == "user" and _PRIVATE.search(turn.text) for turn in turns)


def detect_topic(turns: list[TranscriptTurn]) -> str | None:
    """At most one low-detail notice per call; no diagnosis or emergency triage."""
    for turn in turns:
        if turn.role != "user":
            continue
        for sentence in re.split(r"[.!?।\n]+", turn.text):
            if _FEVER.search(sentence) and not _FEVER_NEGATION.search(sentence):
                return "fever"
            if _BEREAVEMENT.search(sentence) and not _BEREAVEMENT_NEGATION.search(sentence):
                return "bereavement"
    return None
