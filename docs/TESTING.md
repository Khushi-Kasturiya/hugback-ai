# Testing and evaluation

[Project overview](../README.md) · [Development](DEVELOPMENT.md) ·
[Safety](DATA_AND_SAFETY.md)

Use fictional fixtures only. Do not put real conversations, recordings,
addresses, tokens or provider error bodies in fixtures, logs or screenshots.
Installing dependencies can require network access; **offline tests themselves
mock paid provider I/O** and need no live Google/SMTP service.

## Default verification

After the [local setup](../README.md#run-locally), from `backend/`:

```sh
.venv/bin/python -m evals.run --suite offline --output /tmp/hugback-offline-eval.json
```

The evaluator runs the backend regression suite in a subprocess with cloud
routing and credentials overridden for offline tests, then checks each
conversation rubric against known passing/failing examples. It does not edit a
private `.env`. Prefer a clean test checkout without a hosted profile; unset
inherited judge/context flags if you have enabled them in your shell.

For a direct regression run in that clean environment:

```sh
.venv/bin/python -m unittest discover -s tests -q
```

From `frontend/`:

```sh
npm test
npm run typecheck
npm run build
```

The frontend runner compiles isolated libraries and uses Node's test runner;
it does not start a real call. Run the production build in a separate checkout
if a development server is using `.next`. A compiled hosted URL is not a live
browser connectivity test.

The backend deployment-profile test may skip when private `.env` is absent.
The real-emulator test is deliberately opt-in. Report actual pass/fail/skip
counts from your run rather than copying historic counts into the README.

## Coverage worth inspecting

| Area | Representative source |
| --- | --- |
| Public/restricted admission, Origin and token gates | [Remote demo](../backend/tests/test_remote_demo.py), [Firestore selection](../backend/tests/test_firestore_selection.py) |
| Independent recipients, revisions and call leases | [Recipients](../backend/tests/test_demo_recipients.py), [demo](../backend/tests/test_demo.py) |
| Four-stage broker and permission boundaries | [Workflow broker](../backend/tests/test_workflow_broker.py), [boundaries](../backend/tests/test_workflow_boundaries.py) |
| Evidence, cooldown, recovery and privacy | [Follow-ups](../backend/tests/test_followups.py), [integration](../backend/tests/test_followup_integration.py) |
| Voice owner isolation, concurrency and expiry | [Firestore voice](../backend/tests/test_firestore_voice.py), [voice portal](../backend/tests/test_voice_portal.py) |
| Summary-only sharing and email failure reporting | [Call summaries](../backend/tests/test_call_summary.py), [alerts](../backend/tests/test_alerts.py) |
| Audio ordering, interruption and subtitle timing | [Backend voice latency](../backend/tests/test_voice_latency.py), [browser playback](../frontend/tests/audio-playback.test.cjs), [subtitles](../frontend/tests/call-subtitles.test.cjs) |
| Browser identity and recipient-scoped UI | [Identity](../frontend/tests/identity.test.cjs), [recipient UI](../frontend/tests/recipient-ui.test.cjs), [history](../frontend/tests/demo-call-history.test.cjs) |
| Internal original intake and partial-write recovery | [Cloud family](../backend/tests/test_cloud_family.py) |

Mock Firestore tests exercise a test double, not production rules/IAM or actual
cloud transaction timing. Offline latency tests verify ordering/bounds, not
real-world voice quality or response time.

## Synthetic acceptance walkthrough

Use the [README tour](../README.md#a-short-demo-tour). Call steps require
separate Google-use approval; they are not part of the offline suite.

| Check | Expected behavior |
| --- | --- |
| Create two fictional recipients | Independent background, consent, memory, calls and voice selection. |
| Prepare a fictional chat | Local preview first; bounded attributed excerpts only after simulated dual permission. File selection alone uploads nothing. |
| Start without an explicit recipient, with a stale revision or foreign ID | Fail closed before provider access. |
| Make a standard-voice call | HugBack names itself, starts naturally and uses approved details sparingly. |
| Ask directly whether it is AI | Honest answer; no claim to be the child or a human. |
| Ask for coding, medical advice or external facts | Brief companion-scope boundary, not a task result; pattern checks are not a universal guarantee. |
| End a call, then start another for the same recipient | Wait for processing; only eligible, consented memory can return. Never claim a failed update succeeded. |
| Switch recipient | No carried-over background preview, subtitles or permission acknowledgement. End active calls first. |
| Enable summary sharing before a new call | A short summary may become available under that recipient/date; no raw turns. |
| Revoke summary sharing | Reads blocked; retained summaries and legacy test turns erased. No fallback to transcript. |
| Leave sharing off during a call | It cannot later recover discarded text merely by enabling sharing. |
| Expire/replace/disable an assigned custom voice | Block stale custom selection; require explicit reassignment or standard choice. |
| Simulate email failure with a mock | Accurate failed/unconfigured state, not a delivery claim. Never send actual email as part of this checklist. |

For an authorized acoustic check, compare the same fictional utterance at normal
and quiet volume, include a natural pause and interrupt once. Inspect capture,
turn-end detection, queued audio and subtitles separately. A text-only Live
evaluation cannot establish microphone quality or voice likeness.

## Evaluation suites

| Suite | Network/cost | What it establishes |
| --- | --- | --- |
| `offline` | No provider requests | Mocked regressions plus good/bad calibration of the scoring rules. |
| `models` | Google; explicit paid opt-in | Planner, Reconciler and Critic outputs on small synthetic cases. |
| `live` | Google; explicit paid opt-in | Multi-turn text-input Live conversations, output transcription and rubric/Critic checks; generated audio is discarded. |

Only after separate authorization:

```sh
# From backend/; these contact Google and may incur charges.
.venv/bin/python -m evals.run --suite models --allow-paid-google --output /tmp/hugback-model-eval.json
.venv/bin/python -m evals.run --suite live --allow-paid-google --output /tmp/hugback-live-eval.json
```

`--repeat 3` performs additional paid requests; supported range is 1–5.
The datasets are [specialist cases](../backend/evals/cases.json) and
[conversation scenarios](../backend/evals/conversation_scenarios.json).
They cover background timing/rotation, scope persistence, quiet requests,
Hindi/Hinglish exchanges, repetition repair and unsupported diagnosis/email
claims. Neither a regex rubric nor the model Critic is a safety certificate.

Reports retain IDs, outcomes, timing, model/prompt/schema/dataset identifiers and
Git commit/dirty state—not generated conversation text. `fail` means a check
failed; `error` means execution/validation failed. Cost is **unmeasured**, not
zero. A passing offline report is not a passing real-model report.

When adding a scenario, give every check a unique name, a passing example and a
failing calibration example with the expected failed rule. Re-run offline
calibration before any paid run; do not weaken an expectation just to get green.

## Optional emulator and operator checks

With the loopback emulator and its explicit profile configured as in
[development](DEVELOPMENT.md#storage-modes):

```sh
HUGBACK_RUN_EMULATOR_TESTS=1 .venv/bin/python -m unittest discover \
  -s tests -p test_firestore_emulator.py -v
```

This writes/deletes its own synthetic emulator records. It must never target a
live database and does not validate production IAM.

`scripts/inspect_demo_quality.py` and `scripts/inspect_demo_tone.py` are trusted
operator diagnostics, not public APIs. They take an owner and server-issued
recipient; Firebase owners use `firebase:UID`. Cloud reads additionally require
`--allow-cloud-read` and separate authorization. Do not expose private Critic
findings through the child portal.

The original-intake CLI's default validation is also offline:

```sh
.venv/bin/python scripts/import_chat_original.py \
  --manifest docs/examples/synthetic-intake.json \
  --file docs/examples/synthetic-chat.txt
```

Expected output includes `cloudAccessed: false` and `contextActive: false`.
Never add cloud execution, SMTP probe or live-voice flags to the default checks.
