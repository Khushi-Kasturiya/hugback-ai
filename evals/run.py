"""Run from repository root: python -m evals.run --suite offline.

Model/live modes contact Google ONLY with --allow-paid-google. Datasets are
bundled synthetic text, never imported files. Reports contain IDs/scores only.
"""
import argparse
import asyncio
import hashlib
import inspect
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).with_name("cases.json")
SCENARIOS = Path(__file__).with_name("conversation_scenarios.json")

from evals.scoring import score_scenario, validate_scenarios

def offline_environment():
    """The developer's cloud profile must not change an offline test's routing."""
    return os.environ | {
        "GEMINI_API_KEY": "synthetic-offline-key",
        "GOOGLE_GENAI_USE_VERTEXAI": "FALSE",
        "GOOGLE_APPLICATION_CREDENTIALS": "",
        "HUGBACK_AUTH_MODE": "development", "LOCAL_DEMO_ENABLED": "FALSE",
        "HUGBACK_DEMO_STORE": "sqlite", "HUGBACK_CLOUD_TEST_ENABLED": "FALSE",
        "HUGBACK_REMOTE_TEST_ENABLED": "FALSE", "HUGBACK_REMOTE_TEST_ORIGIN": "",
        "HUGBACK_PUBLIC_DEMO_ENABLED": "FALSE",
        "HUGBACK_WORKFLOW_ENABLED": "FALSE", "FIRESTORE_EMULATOR_HOST": "",
        "FIRESTORE_ENABLED": "FALSE", "MEMORY_ENABLED": "FALSE",
        "FOLLOWUPS_ENABLED": "FALSE", "CLOUD_INTAKE_ENABLED": "FALSE",
        "PORTAL_SHARING_ENABLED": "FALSE", "HUGBACK_REPLICATED_TTS_ENABLED": "FALSE",
        "HUGBACK_LIVE_VOICE_MODE": "preset", "HUGBACK_RUN_EMULATOR_TESTS": "0",
        "HUGBACK_ALERT_EMAIL_ENABLED": "FALSE", "HUGBACK_ALERT_TEST_TO_VERIFIED": "FALSE",
        "HUGBACK_ALERT_SMTP_USERNAME": "", "HUGBACK_ALERT_SMTP_APP_PASSWORD": "",
        "HUGBACK_ALERT_TEST_TO_EMAIL": "",
    }


@contextmanager
def synthetic_model_scope():
    """No repository access; scope the extractor's gate to this synthetic suite."""
    from app.config import settings
    overrides = dict(LOCAL_DEMO_ENABLED=True, HUGBACK_DEMO_STORE="sqlite",
                     HUGBACK_AUTH_MODE="development", HUGBACK_WORKFLOW_ENABLED=False,
                     FIRESTORE_EMULATOR_HOST=None, HUGBACK_REMOTE_TEST_ENABLED=False,
                     HUGBACK_PUBLIC_DEMO_ENABLED=False)
    previous = {key: getattr(settings, key) for key in overrides}
    emulator = os.environ.pop("FIRESTORE_EMULATOR_HOST", None)
    try:
        for key, value in overrides.items():
            setattr(settings, key, value)
        yield
    finally:
        for key, value in previous.items():
            setattr(settings, key, value)
        if emulator is not None:
            os.environ["FIRESTORE_EMULATOR_HOST"] = emulator


async def model_cases(data):
    with synthetic_model_scope():
        return await _model_cases(data)


async def _model_cases(data):
    from app.memory.models import TranscriptTurn
    from app.memory.followups import CallPlan
    from app.workflows.reconciler import MemoryReconciler
    from app.workflows.planner import ConversationPlanner
    from app.workflows.critic import QualityCritic
    from app.workflows.contracts import ToolOutcome
    results = []
    async def measure(case_id, check):
        started = time.monotonic()
        try:
            passed = bool(await check())
            outcome = "pass" if passed else "fail"
        except Exception:
            outcome = "error"  # Never include private/provider response bodies.
        results.append({"id": case_id, "outcome": outcome, "seconds": round(time.monotonic()-started, 3)})
    for case in data["memory"]:
        async def check():
            turns = [TranscriptTurn(role="user", turn_index=0, text=case["text"])]
            plan = CallPlan(session_id="synthetic-eval", consent=True, generation=1, time_zone="Asia/Kolkata")
            batch = await MemoryReconciler(local_demo=True).extract(turns, plan)
            return (sorted([[o.topic, o.action] for o in batch.observations]) == sorted(case["expected"])
                    and all(o.source_turn == 0 and o.evidence in case["text"] and o.evidence.strip()
                            for o in batch.observations))
        await measure("memory/"+case["id"], check)
    for case in data["planner"]:
        async def check():
            state = {"language": case["language"], "background": case["background"]}
            plan = await ConversationPlanner().prepare(state, None)
            return (not plan.consider_followup and plan.language == case["language"]
                    and plan.background_refs == case["expectedRefs"])
        await measure("planner/"+case["id"], check)
    for case in data["critic"]:
        async def check():
            turns = [TranscriptTurn(role="user", turn_index=0, text=case["user"]),
                     TranscriptTurn(role="model", turn_index=1, text=case["assistant"])]
            report = await QualityCritic().evaluate(turns, [ToolOutcome(**t) for t in case.get("tools", [])],
                                                    background=[], language="en")
            codes = {f.code for f in report.findings}
            return not report.uncertain and codes == set(case["expected"])
        await measure("critic/"+case["id"], check)
    return results

async def live_cases(scenarios):
    from app.agent.live_session import create_genai_client, create_live_config
    from google.genai import types
    from app.config import settings
    from app.demo.service import background_context
    from app.memory.models import TranscriptTurn
    from app.memory.transcript import merge_transcription
    from app.workflows.critic import QualityCritic
    from app.workflows.contracts import ConversationPlan
    from app.workflows.planner import plan_context, planner_payload, validate_plan
    results = []
    for scenario in scenarios:
        started = time.monotonic()
        client = None
        try:
            # Each call is a fresh Live session. Only fictional text is sent;
            # output audio is discarded and never scored as acoustic evidence.
            client = create_genai_client()
            replies_by_call = []
            all_turns = []
            for call_index, call in enumerate(scenario["calls"]):
                background = [item | {"reviewedAt": "2026-10-12T12:00:00+00:00"}
                              for item in scenario.get("background", [])]
                state = {
                    "label": scenario.get("label", "Parent"),
                    "relationship": scenario.get("relationship", "other"),
                    "timeZone": "Asia/Kolkata", "language": "en",
                    "background": background, "backgroundCallCount": call_index + 1,
                    "calls": [],
                }
                plan = None
                if "planRef" in call:
                    plan = validate_plan(
                        ConversationPlan(language="en", background_refs=[call["planRef"]]),
                        planner_payload(state, None),
                    )
                config = create_live_config(
                    background_context=background_context(state) if background else "",
                    conversation_plan_context=plan_context(plan, state),
                    preferred_language=state["language"],
                )
                replies = []
                async with asyncio.timeout(90):
                    async with client.aio.live.connect(model=settings.HUGBACK_MODEL, config=config) as live:
                        for message in call["messages"]:
                            text = ""
                            all_turns.append(TranscriptTurn(role="user", turn_index=len(all_turns), text=message))
                            await live.send_client_content(
                                turns=types.Content(role="user", parts=[types.Part.from_text(text=message)]),
                                turn_complete=True)
                            async for response in live.receive():
                                if response.tool_call:
                                    raise ValueError("No tools authorized in this eval scenario")
                                content = response.server_content
                                if content and content.output_transcription:
                                    text = merge_transcription(text, content.output_transcription.text or "")
                            replies.append(text)
                            all_turns.append(TranscriptTurn(role="model", turn_index=len(all_turns), text=text or " "))
                replies_by_call.append(replies)
            for check in score_scenario(scenario, replies_by_call):
                results.append({"id": f"live/{scenario['id']}/{check['id']}",
                                "outcome": "pass" if check["passed"] else "fail"})
            # The judge adds a qualitative backstop; it is not the sole score.
            report = await QualityCritic().evaluate(
                all_turns, [], background=scenario.get("background", []), language="en")
            results.append({"id": f"live/{scenario['id']}/critic",
                            "outcome": "pass" if not report.findings and not report.uncertain else "fail",
                            "seconds": round(time.monotonic()-started, 3)})
        except Exception:
            results.append({"id": f"live/{scenario['id']}/execution", "outcome": "error"})
        finally:
            if client:
                await client.aio.aclose()
                client.close()
    return results

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["offline", "models", "live"], default="offline")
    parser.add_argument("--allow-paid-google", action="store_true")
    parser.add_argument("--repeat", type=int, default=1,
                        help="Explicitly repeat each paid case 1-5 times; each repeat makes new Google requests")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not 1 <= args.repeat <= 5:
        parser.error("--repeat must be between 1 and 5")
    if args.suite == "offline" and args.repeat != 1:
        parser.error("--repeat applies only to paid models/live suites")
    if args.suite != "offline" and not args.allow_paid_google:
        parser.error("models/live require --allow-paid-google; synthetic requests may incur charges")
    raw = DATA.read_bytes(); data = json.loads(raw)
    scenario_raw = SCENARIOS.read_bytes(); scenarios = json.loads(scenario_raw)["scenarios"]
    validate_scenarios(scenarios)
    started = time.monotonic()
    if args.suite == "offline":
        # Full tests include mocked broker, voice, privacy, storage and workflow paths.
        process = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
                                 cwd=ROOT, env=offline_environment())
        results = [{"id": "offline/regression_suite", "outcome": "pass" if process.returncode == 0 else "fail"}]
        for scenario in scenarios:
            results.extend({"id": f"offline/scorer/{scenario['id']}/{check['id']}",
                            "outcome": "pass" if check["passed"] else "fail"}
                           for check in score_scenario(scenario, scenario["calibration"]["good"]))
            for variant in scenario["calibration"]["bad"]:
                caught = {check["id"] for check in score_scenario(scenario, variant["replies"])
                          if not check["passed"]}
                results.append({"id": f"offline/scorer/{scenario['id']}/catches_{variant['id']}",
                                "outcome": "pass" if set(variant["mustFail"]).issubset(caught) else "fail"})
    else:
        results = []
        for repeat in range(1, args.repeat + 1):
            batch = asyncio.run(model_cases(data) if args.suite == "models" else live_cases(scenarios))
            results.extend(item | {"id": f"run{repeat}/{item['id']}"} for item in batch)
    from app.config import settings
    from app.workflows.planner import INSTRUCTION as PLANNER
    from app.workflows.critic import INSTRUCTION as CRITIC
    from app.memory.followup_extractor import INSTRUCTION as RECONCILER
    from app.agent.prompts import HUGBACK_SYSTEM_INSTRUCTION
    from app.demo.service import background_context
    from app.workflows.planner import plan_context
    from app.workflows.contracts import ConversationPlan, CritiqueReport
    from app.memory.followups import ObservationBatch
    report = {
        "suite": args.suite, "syntheticOnly": True, "dataset": data["version"],
        "scenarioDataset": json.loads(scenario_raw)["version"], "repeat": args.repeat,
        "datasetSha256": hashlib.sha256(raw + scenario_raw).hexdigest(),
        "promptSha256": hashlib.sha256((PLANNER+CRITIC+RECONCILER+HUGBACK_SYSTEM_INSTRUCTION
                                         + inspect.getsource(background_context)
                                         + inspect.getsource(plan_context)).encode()).hexdigest(),
        "schemaSha256": hashlib.sha256(json.dumps(
            [s.model_json_schema() for s in (ConversationPlan, ObservationBatch, CritiqueReport)],
            sort_keys=True).encode()).hexdigest(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
        "models": {"live": settings.HUGBACK_MODEL, "text": settings.FOLLOWUP_EXTRACTION_MODEL},
        "createdAt": datetime.now(timezone.utc).isoformat(), "results": results,
        "passed": all(r["outcome"] == "pass" for r in results),
        "counts": {outcome: sum(r["outcome"] == outcome for r in results) for outcome in ("pass", "fail", "error")},
        "seconds": round(time.monotonic()-started, 3), "cost": "not measured",
        "limitations": ["Offline scorer calibration is not a model-quality result",
                        "Live uses text input and discards audio; no microphone, timing or voice assessment",
                        "Regex checks cover named synthetic examples only; Critic can be wrong",
                        "Not production IAM, enrollment, delivery or phone validation"],
    }
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(text+"\n")
    print(text)
    return 0 if report["passed"] else 1

if __name__ == "__main__": raise SystemExit(main())
