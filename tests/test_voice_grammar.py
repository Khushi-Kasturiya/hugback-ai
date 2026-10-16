"""Explicit child detail controls custom-voice grammar; no audio processing."""

import unittest

from app.voice.grammar import speaking_form_for_call


class VoiceGrammarTests(unittest.TestCase):
    def test_standard_voice_always_uses_feminine_form(self):
        for child_gender in (None, "female", "male", "neutral"):
            self.assertEqual(speaking_form_for_call(
                custom_voice=False, child_gender=child_gender), "feminine")

    def test_custom_voice_uses_saved_child_details(self):
        for gender, form in (("male", "masculine"), ("female", "feminine"),
                             ("neutral", "neutral"), (None, "neutral")):
            self.assertEqual(speaking_form_for_call(
                custom_voice=True, child_gender=gender), form)


if __name__ == "__main__":
    unittest.main()
