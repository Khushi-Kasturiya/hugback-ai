"""Run from repository root: python -m evals.run --suite offline.

Model/live modes contact Google ONLY with --allow-paid-google. Datasets are
bundled synthetic text, never imported files. Reports contain IDs/scores only.
"""
import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).with_name("cases.json")

def offline_environment():
    """The developer's cloud profile must not change an offline test's routing."""
    return os.environ | {
        "GEMINI_API_KEY": "synthetic-offline-key",
        "GOOGLE_GENAI_USE_VERTEXAI": "FALSE",
        "GOOGLE_APPLICATION_CREDENTIALS": "",
        "HUGBACK_AUTH_MODE": "development", "LOCAL_DEMO_ENABLED": "FALSE",
        "HUGBACK_DEMO_STORE": "sqlite", "HUGBACK_CLOUD_TEST_ENABLED": "FALSE",
        "HUGBACK_WORKFLOW_ENABLED": "FALSE", "FIRESTORE_EMULATOR_HOST": "",
        "FIRESTORE_ENABLED": "FALSE", "MEMORY_ENABLED": "FALSE",
        "FOLLOWUPS_ENABLED": "FALSE", "CLOUD_INTAKE_ENABLED": "FALSE",
        "PORTAL_SHARING_ENABLED": "FALSE", "HUGBACK_REPLICATED_TTS_ENABLED": "FALSE",
        "HUGBACK_LIVE_VOICE_MODE": "preset", "HUGBACK_RUN_EMULATOR_TESTS": "0",
    }


@contextmanager
def synthetic_model_scope():
    """No repository access; scope the extractor's gate to this synthetic suite."""
    from app.config import settings
    overrides = dict(LOCAL_DEMO_ENABLED=True, HUGBACK_DEMO_STORE="sqlite",
                     HUGBACK_AUTH_MODE="development", HUGBACK_WORKFLOW_ENABLED=False,
                     FIRESTORE_EMULATOR_HOST=None)
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
    for language in ("auto", "en", "hi", "hi-en"):
        async def check():
            plan = await ConversationPlanner().prepare({"language": language, "background": [{
                "role": "parent", "timestamp": "2026-10-01", "text": "I enjoy fictional gardening."}]}, None)
            return not plan.consider_followup and plan.language == language
        await measure("planner/"+language, check)
    for case in data["critic"]:
        async def check():
            turns = [TranscriptTurn(role="user", turn_index=0, text=case["user"]),
                     TranscriptTurn(role="model", turn_index=1, text=case["assistant"])]
            report = await QualityCritic().evaluate(turns, [ToolOutcome(**t) for t in case.get("tools", [])],
                                                    background=[], language="en")
            codes = {f.code for f in report.findings}
            return (not report.uncertain and (set(case["expected"]) <= codes if case["expected"] else not codes))
        await measure("critic/"+case["id"], check)
    return results

async def live_cases(data):
    from app.agent.live_session import create_genai_client, create_live_config
    from app.config import settings
    from app.memory.models import TranscriptTurn
    from app.workflows.critic import QualityCritic
    results = []
    for case in data["live"]:
        started = time.monotonic()
        client = None
        try:
            # Actual Live config and transport; synthetic text in, audio discarded.
            client = create_genai_client()
            async with asyncio.timeout(45):
                async with client.aio.live.connect(model=settings.HUGBACK_MODEL, config=create_live_config()) as live:
                    turns = []
                    for message in case["messages"]:
                        model_text = ""
                        turns.append(TranscriptTurn(role="user", turn_index=len(turns), text=message))
                        await live.send_client_content(turns={"role": "user", "parts": [{"text": message}]}, turn_complete=True)
                        async for response in live.receive():
                            if response.tool_call:
                                raise ValueError("No tools authorized in this eval scenario")
                            content = response.server_content
                            if content and content.output_transcription:
                                model_text += content.output_transcription.text or ""
                        turns.append(TranscriptTurn(role="model", turn_index=len(turns), text=model_text))
                    report = await QualityCritic().evaluate(turns, [], background=[], language="en")
                    # Simple deterministic check complements (does not replace)
                    # the fallible model judge. These live fixtures request English.
                    spoken = " ".join(t.text for t in turns if t.role == "model")
                    disclosure = bool(re.search(r"\b(?:AI|artificial intelligence)\b", spoken, re.I))
                    passed = disclosure and bool(model_text.strip()) and not report.findings and not report.uncertain
                    results.append({"id": "live/"+case["id"], "outcome": "pass" if passed else "fail",
                                    "seconds": round(time.monotonic()-started, 3)})
        except Exception:
            results.append({"id": "live/"+case["id"], "outcome": "error"})
        finally:
            if client:
                await client.aio.aclose(); client.close()
    return results

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["offline", "models", "live"], default="offline")
    parser.add_argument("--allow-paid-google", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.suite != "offline" and not args.allow_paid_google:
        parser.error("models/live require --allow-paid-google; synthetic requests may incur charges")
    raw = DATA.read_bytes(); data = json.loads(raw)
    started = time.monotonic()
    if args.suite == "offline":
        # Full tests include mocked broker, voice, privacy, storage and workflow paths.
        process = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
                                 cwd=ROOT, env=offline_environment())
        results = [{"id": "offline/regression_suite", "outcome": "pass" if process.returncode == 0 else "fail"}]
    else:
        results = asyncio.run(model_cases(data) if args.suite == "models" else live_cases(data))
    from app.config import settings
    from app.workflows.planner import INSTRUCTION as PLANNER
    from app.workflows.critic import INSTRUCTION as CRITIC
    from app.memory.followup_extractor import INSTRUCTION as RECONCILER
    from app.agent.prompts import HUGBACK_SYSTEM_INSTRUCTION
    from app.workflows.contracts import ConversationPlan, CritiqueReport
    from app.memory.followups import ObservationBatch
    report = {
        "suite": args.suite, "syntheticOnly": True, "dataset": data["version"],
        "datasetSha256": hashlib.sha256(raw).hexdigest(),
        "promptSha256": hashlib.sha256((PLANNER+CRITIC+RECONCILER+HUGBACK_SYSTEM_INSTRUCTION).encode()).hexdigest(),
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
        "limitations": ["Not an acoustic likeness assessment", "Not production IAM or phone enrollment validation",
                        "Small synthetic dataset; critic judge requires human calibration"],
    }
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(text+"\n")
    print(text)
    return 0 if report["passed"] else 1

if __name__ == "__main__": raise SystemExit(main())
