"""Choose HugBack's first-person grammar from explicit setup, never audio."""


def speaking_form_for_call(*, custom_voice: bool, child_gender: str | None) -> str:
    if not custom_voice:
        return "feminine"
    return {"male": "masculine", "female": "feminine", "neutral": "neutral"}.get(
        child_gender, "neutral",
    )
