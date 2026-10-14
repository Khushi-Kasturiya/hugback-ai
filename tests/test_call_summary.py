"""Call summaries use bounded synthetic turns and never expose raw fallback."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.demo.summary import INSTRUCTION, summarize_call, summary_input
from app.memory.models import TranscriptTurn


def turns():
    return [
        TranscriptTurn(role="user", turn_index=0, text="I painted blue flowers today."),
        TranscriptTurn(role="model", turn_index=1, text="That sounds lovely. What colours did you use?"),
    ]


class SummaryTests(unittest.IsolatedAsyncioTestCase):
    def test_summary_guidance_adds_detail_only_when_supported(self):
        self.assertIn("two or three concise", INSTRUCTION)
        self.assertIn("one other meaningful detail", INSTRUCTION)
        self.assertIn("how HugBack responded", INSTRUCTION)
        self.assertIn("one accurate sentence is enough", INSTRUCTION)

    async def test_grounded_short_summary(self):
        provider = SimpleNamespace(generate=AsyncMock(return_value=SimpleNamespace(
            summary="  Mother described painting blue flowers.  HugBack asked about the colours. ",
            source_turns=[0, 1],
        )))
        result = await summarize_call(turns(), provider=provider)
        self.assertEqual(result, "Mother described painting blue flowers. HugBack asked about the colours.")
        provider.generate.assert_awaited_once()

    async def test_invalid_evidence_and_provider_failure_fail_closed(self):
        bad = SimpleNamespace(generate=AsyncMock(return_value=SimpleNamespace(
            summary="Mother described painting blue flowers.", source_turns=[42],
        )))
        self.assertIsNone(await summarize_call(turns(), provider=bad))
        assistant_only = SimpleNamespace(generate=AsyncMock(return_value=SimpleNamespace(
            summary="HugBack discussed painting with the caller.", source_turns=[1],
        )))
        self.assertIsNone(await summarize_call(turns(), provider=assistant_only))
        copied_turn = SimpleNamespace(generate=AsyncMock(return_value=SimpleNamespace(
            summary="HugBack said: That sounds lovely. What colours did you use?",
            source_turns=[0, 1],
        )))
        self.assertIsNone(await summarize_call(turns(), provider=copied_turn))
        failed = SimpleNamespace(generate=AsyncMock(side_effect=RuntimeError("synthetic provider failure")))
        self.assertIsNone(await summarize_call(turns(), provider=failed))

    async def test_missing_speaker_skips_model_and_long_call_is_bounded(self):
        provider = SimpleNamespace(generate=AsyncMock())
        self.assertIsNone(await summarize_call([turns()[0]], provider=provider))
        provider.generate.assert_not_awaited()
        long_turns = [TranscriptTurn(role="user", turn_index=0, text="I painted flowers. " * 2000), turns()[1]]
        bounded = summary_input(long_turns)
        self.assertLessEqual(sum(len(turn.text) for turn in bounded), 15_100)
        self.assertEqual([turn.turn_index for turn in bounded], [0, 1])
        self.assertEqual(len(long_turns[0].text), len("I painted flowers. " * 2000))
        provider.generate.return_value = SimpleNamespace(
            summary="Mother discussed painting flowers with HugBack.", source_turns=[0])
        self.assertEqual(await summarize_call(long_turns, provider=provider),
                         "Mother discussed painting flowers with HugBack.")
        self.assertLessEqual(len(provider.generate.call_args.args[1]["turns"][0]["text"]), 1500)


if __name__ == "__main__":
    unittest.main()
