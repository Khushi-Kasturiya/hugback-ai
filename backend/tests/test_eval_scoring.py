"""Offline calibration: every named conversation rule catches a known failure."""

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.workflows.contracts import ConversationPlan
from app.workflows.planner import planner_payload, validate_plan
from evals.scoring import score_scenario, validate_scenarios


SCENARIOS = json.loads((Path(__file__).resolve().parents[1] / "evals" /
                        "conversation_scenarios.json").read_text())["scenarios"]


class ConversationEvalScoringTests(unittest.TestCase):
    def test_all_scenarios_have_good_and_bad_calibration(self):
        validate_scenarios(SCENARIOS)
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario["id"]):
                self.assertTrue(all(item["passed"] for item in score_scenario(
                    scenario, scenario["calibration"]["good"])))
                for variant in scenario["calibration"]["bad"]:
                    failed = {item["id"] for item in score_scenario(scenario, variant["replies"])
                              if not item["passed"]}
                    self.assertTrue(set(variant["mustFail"]).issubset(failed))

    def test_background_plans_are_grounded_and_rotate(self):
        for scenario in SCENARIOS:
            for call_index, call in enumerate(scenario["calls"]):
                if "planRef" not in call:
                    continue
                state = {"language": "en", "background": scenario["background"],
                         "backgroundCallCount": call_index + 1, "calls": []}
                plan = ConversationPlan(language="en", background_refs=[call["planRef"]])
                with self.subTest(scenario=scenario["id"], call=call_index):
                    self.assertEqual(validate_plan(plan, planner_payload(state, None)), plan)

    def test_missing_replies_fail_even_if_other_checks_are_easy(self):
        scenario = SCENARIOS[0]
        self.assertEqual(score_scenario(scenario, [[] for _ in scenario["calls"]]),
                         [{"id": "call1/reply_count", "passed": False},
                          {"id": "call2/reply_count", "passed": False}])

    def test_paid_eval_requires_explicit_flag(self):
        from evals.run import main
        for suite in ("models", "live"):
            with self.subTest(suite=suite), self.assertRaises(SystemExit) as raised:
                main(["--suite", suite])
            self.assertEqual(raised.exception.code, 2)


class LiveEvalTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_call_scenario_uses_mocked_live_and_scores_each_reply(self):
        from evals.run import live_cases

        scenario = SCENARIOS[0]
        good = scenario["calibration"]["good"]

        class FakeSession:
            def __init__(self, replies):
                self.replies = iter(replies)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                return False

            async def send_client_content(self, **kwargs):
                self.last_turn = kwargs["turns"]

            async def receive(self):
                yield SimpleNamespace(tool_call=None, server_content=SimpleNamespace(
                    output_transcription=SimpleNamespace(text=next(self.replies))))

        class FakeLive:
            def __init__(self):
                self.call = 0

            def connect(self, **_):
                session = FakeSession(good[self.call])
                self.call += 1
                return session

        class FakeClient:
            def __init__(self):
                self.live = FakeLive()
                self.aio = SimpleNamespace(live=self.live, aclose=AsyncMock())

            def close(self):
                pass

        with patch("app.agent.live_session.create_genai_client", return_value=FakeClient()), patch(
            "app.workflows.critic.QualityCritic.evaluate", new=AsyncMock(
                return_value=SimpleNamespace(findings=[], uncertain=False))):
            results = await live_cases([scenario])
        self.assertTrue(all(result["outcome"] == "pass" for result in results), results)
        self.assertIn("live/background_rotates_across_calls/call2/music_bridge",
                      {result["id"] for result in results})
        self.assertTrue(all(set(result) <= {"id", "outcome", "seconds"} for result in results))


if __name__ == "__main__":
    unittest.main()
