"""Small, auditable rubrics for fictional multi-turn Live evaluations.

Rules are deliberately narrow: passing them is evidence for the named behavior,
not a general judgment of conversation quality or safety. No raw reply is logged.
"""

import re


def _matches(reply: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, reply, re.IGNORECASE | re.UNICODE) for pattern in patterns)


def score_call(call: dict, replies: list[str]) -> list[dict]:
    """Return one content-free pass/fail result per explicit check."""
    messages = call["messages"]
    if len(replies) != len(messages):
        return [{"id": "reply_count", "passed": False}]
    results = []
    for rule in call["checks"]:
        kind = rule["kind"]
        start = rule.get("from", 0)
        end = rule.get("through", len(replies) - 1)
        if not isinstance(start, int) or not isinstance(end, int) or not (0 <= start <= end < len(replies)):
            raise ValueError("Invalid eval reply range")
        window = replies[start:end + 1]
        if kind == "first_named_identity":
            passed = (bool(re.search(r"\bHugback\b", replies[0], re.I))
                      and not bool(re.search(r"\b(?:AI|artificial intelligence)\b", replies[0], re.I))
                      and not bool(re.search(r"\b(?:son|daughter|child)\b", replies[0], re.I)))
        elif kind == "all_nonempty":
            passed = all(reply.strip() for reply in replies)
        elif kind == "any":
            passed = any(_matches(reply, rule["patterns"]) for reply in window)
        elif kind == "none":
            passed = not any(_matches(reply, rule["patterns"]) for reply in window)
        elif kind == "count":
            count = sum(_matches(reply, rule["patterns"]) for reply in window)
            passed = rule.get("min", 0) <= count <= rule.get("max", len(window))
        elif kind == "max_questions":
            passed = all(reply.count("?") + reply.count("？") + reply.count("؟") <= rule["max"]
                         for reply in window)
        elif kind == "distinct_topics":
            found = []
            for index in rule["replies"]:
                if not isinstance(index, int) or not 0 <= index < len(replies):
                    raise ValueError("Invalid eval topic reply index")
                topics = [name for name, patterns in rule["topics"].items()
                          if _matches(replies[index], patterns)]
                found.append(topics)
            passed = all(len(topics) == 1 for topics in found) and len({topics[0] for topics in found}) == len(found)
        else:
            raise ValueError("Unknown eval check kind")
        results.append({"id": rule["id"], "passed": bool(passed)})
    return results


def score_scenario(scenario: dict, call_replies: list[list[str]]) -> list[dict]:
    if len(call_replies) != len(scenario["calls"]):
        return [{"id": "call_count", "passed": False}]
    return [{"id": f"call{number}/{result['id']}", "passed": result["passed"]}
            for number, (call, replies) in enumerate(zip(scenario["calls"], call_replies), 1)
            for result in score_call(call, replies)]


def validate_scenarios(scenarios: list[dict]) -> None:
    seen = set()
    for scenario in scenarios:
        if scenario["id"] in seen or not scenario["calls"]:
            raise ValueError("Duplicate or empty eval scenario")
        seen.add(scenario["id"])
        good = scenario["calibration"]["good"]
        if not all(item["passed"] for item in score_scenario(scenario, good)):
            raise ValueError(f"Good calibration fails: {scenario['id']}")
        bad = scenario["calibration"]["bad"]
        if not bad:
            raise ValueError("Each eval scenario needs a known bad transcript")
        for variant in bad:
            failed = {item["id"] for item in score_scenario(scenario, variant["replies"])
                      if not item["passed"]}
            if not set(variant["mustFail"]).issubset(failed):
                raise ValueError(f"Bad calibration was not caught: {scenario['id']}/{variant['id']}")
