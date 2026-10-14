"""Offline examples for the narrow pre-playback entertainment gate."""

import unittest

from app.agent.scope_gate import EntertainmentScopeGate


class EntertainmentScopeGateTests(unittest.TestCase):
    def test_direct_show_questions_are_blocked_without_previous_context(self):
        for question in (
            "Do you know Taarak Mehta Ka Ooltah Chashmah?",
            "Do you know this TV show?",
            "Tell me about Drishyam movie.",
            "Taarak Mehta kaisa show hai?",
            "क्या तुम्हें इस शो के बारे में पता है?",
        ):
            with self.subTest(question=question):
                self.assertIsNotNone(EntertainmentScopeGate().inspect(question))

    def test_other_information_requests_are_blocked(self):
        for question in (
            "Who is the president?", "Explain photosynthesis.",
            "Can you write C++ code?", "How do I fix Wi-Fi?",
            "Which phone should I buy?", "What is gravity?",
            "Can you search it for me?", "Tell me about Rahul Gandhi.",
        ):
            with self.subTest(question=question):
                self.assertIsNotNone(EntertainmentScopeGate().inspect(question))

    def test_personal_conversation_and_background_questions_continue(self):
        gate = EntertainmentScopeGate()
        for text in (
            "I watched Taarak Mehta today.", "I liked that show.",
            "Do you know what I like?", "What is my background?",
            "My daughter likes coding.", "The movie made me laugh.",
        ):
            with self.subTest(text=text):
                self.assertIsNone(gate.inspect(text))

    def test_personal_show_chat_then_character_fact_question(self):
        gate = EntertainmentScopeGate()
        self.assertIsNone(gate.inspect("Kuch nahi, bas TV dekh rahe hain."))
        self.assertIsNone(gate.inspect("Haan, Taarak Mehta Ka Ooltah Chashmah dekh raha tha."))
        reply = gate.inspect("Haan, iske kirdaar ke baare mein tumhe pata hai kya?")
        self.assertIn("facts", reply)
        self.assertNotIn("Jethalal", reply)

    def test_hindi_and_english_fact_requests_without_title_memory(self):
        self.assertIn("तथ्य", EntertainmentScopeGate().inspect(
            "इस टीवी शो के किरदार के बारे में तुम्हें पता है क्या?"))
        self.assertIn("facts", EntertainmentScopeGate().inspect(
            "Who is the actor in this TV show?"))
        self.assertIsNotNone(EntertainmentScopeGate().inspect("Drishyam kaisi movie hai?"))

    def test_exact_hindi_show_exchange_from_report(self):
        gate = EntertainmentScopeGate()
        self.assertIsNone(gate.inspect("हाँ, तारक मेहता का उल्टा चश्मा देख रहा था।"))
        reply = gate.inspect("हाँ, कुछ बताना यार। इसके किरदार के बारे में तुम्हें पता है क्या?")
        self.assertIn("तथ्य", reply)
        self.assertNotIn("जेठालाल", reply)

    def test_personal_opinion_does_not_trigger_search_boundary(self):
        gate = EntertainmentScopeGate()
        self.assertIsNone(gate.inspect("I watched a movie today."))
        self.assertIsNone(gate.inspect("I liked the characters."))
        self.assertIsNone(gate.inspect("Mera favourite character Jethalal hai."))

    def test_old_show_context_expires(self):
        gate = EntertainmentScopeGate()
        gate.inspect("I watched a show.")
        for text in ("I made tea.", "I spoke with a friend.", "I went outside.", "Now I am resting."):
            self.assertIsNone(gate.inspect(text))
        self.assertIsNone(gate.inspect("Which character are you talking about?"))
