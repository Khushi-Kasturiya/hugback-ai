# HugBack / Elara: work completed in this chat

**Recorded:** 13 October 2026
**Repositories:** `elara.ai-backend`, sibling `elara.ai-frontend`, and the `Documents/ChatGPT/ELARA` architecture workspace
**Scope:** the local hackathon simulator and its architecture. This document describes the inspected implementation and the changes made during this conversation; it is not evidence of a production launch or a successful real email/telephone call.

**Latest Signals back revision (13 October):** the user changed the history view
from full raw conversation text to a short AI-generated call summary. New
fictional calls with the separate sharing setting can produce a bounded summary;
the child portal fetches only that summary through
`GET /api/demo/summaries/{recipient_id}/{session_id}`. The former raw-turn route
is removed. New call-history turns are processed ephemerally and not persisted.
Older calls with saved synthetic text can be converted by an explicit action;
others display unavailable. Model failure never falls back to raw text. The
former full-transcript design has been replaced throughout this record.

**Later voice and address check (13 October):** the selected fictional recipient
in the local family data was labeled `Mumma` and configured for the standard
HugBack voice. The backend chooses one preset voice (`Aoede` in the private
local configuration) when a Live call connects; there is no mid-call switch to
an assigned child voice in this path. The Live prompt now asks for a natural
recipient form of address once in the second or third reply and at most once
more later, while honoring a request to stop. It also asks the model to clarify
unclear English/Hindi words and avoid repeated clauses. Streaming caption
assembly now merges cumulative and overlapping chunks in the browser and in
the transient backend collector; these changes do not guarantee that Google
Live will never vary its generated timbre or repeat spoken words. The call UI
identifies standard and assigned voices accurately. Offline tests passed;
no paid Live voice test or real family call was run for this check.

**Companion scope revision (13 October):** a fictional Live call respected the
C++ request boundary but then gave a short factual answer about a politician.
The Live prompt now explicitly keeps HugBack in personal conversation and
rules out political facts, opinions, current-affairs explanations and other
general task answers, including follow-up requests such as "you tell me".
Personal stories involving a vote or news can still be heard without political
commentary. The post-call Quality Critic can report `out_of_scope_answer` for
an assistant reply that crosses this boundary; it cannot stop streamed audio.
The beginner test guide includes direct and indirect political prompts. This
revision was checked offline only; model compliance in a real Live call remains
to be verified by listening with fictional content.

**Broader companion guardrails (13 October, later revision):** After reviewing
the local John-Keats reference, we used its general separation of a companion
role, a short boundary response, and safety exceptions as design inspiration;
we did not copy its persona, scripts, or policy-gate code. HugBack's own Live
instruction now classifies the *requested action*: producing a deliverable,
instructions, facts, analysis, recommendations, persuasion, or decisions is
outside its role across topics such as travel, shopping, homework, coding,
message writing, science, politics, and professional advice. It forbids partial
answers and keeps the same boundary across follow-ups, role-play, quoted text,
claimed permission, and language switches. Personal stories involving those
topics remain welcome. Immediate danger and self-harm get a safety response,
not a routine scope refusal. The synthetic post-call Critic prompt and eval
fixtures now cover these categories, including a personal-story negative case.
Because native Live audio is streamed before a post-call review, this is still
prompt-guided behavior, not a deterministic pre-speech block. Only offline
checks were run for this revision; no real family data or paid Live eval was
used. Manual fictional-call cases are in the beginner testing guide.

**Recipient address follow-up (13 October):** In a fictional Mumma call, Live
received the selected label but did not speak it at all. The former context
said to use it only if natural in the second or third reply, which allowed
omission. The synthetic call context now asks for one deliberate use around
the fourth to sixth spoken reply, after the greeting, with at most one later
use in a long call. It prevents adjacent or suffix-like repetition, excludes
generic profile labels, and honors a direct request to stop. The label remains
an untrusted selected demo field, not speaker verification or a relationship
claim. Offline tests verify that this guidance reaches Live; only a new
fictional listening test can show whether the model follows it in speech.

**One-action fictional chat background (13 October):** The per-message checkbox
screen confused the user because the selected parent's uploaded chat should
prepare background without manual curation. The browser now considers every
parent-authored text message after the user identifies both participants and
confirms whole-chat synthetic child/parent permissions. It deterministically
spreads up to 24 dated excerpts across the entire parsed conversation and
shortens each to 500 characters before a recipient-scoped revisioned backend
save. Child-authored messages and the original TXT are not sent as call context.
The screen states that larger exports are represented by bounded excerpts,
not fully recalled or summarized. Planner still considers one parent-authored
excerpt per call for a possible later bridge, and the Live agent may answer
direct background questions from the bounded prepared set. Real-family intake
and verified dual consent are unchanged. This action makes no paid model call.

**Natural background bridge follow-up (13 October):** A fictional call showed
that HugBack answered questions about painting and songs when pressed but did
not volunteer the one planned interest after several turns. It also treated
“tell me something interesting” as a trivia request and fell back to generic
hobby questions. The pre-call candidate rotation now prefers explicit
parent-authored interests over logistical messages when available; the Planner
still rejects an unsuitable or sensitive candidate. Live guidance asks for one
natural question about the selected interest after roughly four to six
exchanges or an invitation to lead, while respecting an active topic, quiet
request or refusal. It forbids a second unsolicited background topic in that
call. A direct background question can receive another supported detail in a
later reply rather than a repeated fact or a full list. This remains
prompt-guided native audio, not deterministic per-turn speech enforcement;
offline tests do not prove spoken compliance. A read-only check of the local
synthetic Mumma call metadata found recent Planner stages marked `fallback`.
The workflow now supplies a narrow deterministic fallback plan for an explicit
parent-authored ordinary interest (for example, painting or songs) when the
Google Planner fails, while abstaining on health, financial, instruction-like
or uncertain text. The stage still reports `fallback`; it does not claim a
successful model plan. This lets the safe one-topic cue reach Live in the
observed fictional Mumma setup without another paid model request.

**Optional voice-tone continuity (13 October):** Family setup now has a separate
simulated consent switch for gentle tone check-ins. When enabled for a selected
fictional recipient, Live may make one tentative in-call observation only after
clear current vocal evidence. The existing bounded signal tool may propose an
after-call category. The backend saves one note for up to 72 hours only when
the model marks it high confidence, explicitly cites vocal cues, and at least
two substantial user turns were captured. The next call under the same selected
recipient gets only that bounded category as tentative context. Disabling the
setting erases it and invalidates in-flight writes. No audio, voiceprint,
acoustic feature or transcript is retained for tone continuity; it does not
identify a speaker, appear as a child-facing signal without separate sharing,
or trigger email. Offline broker/store/UI tests pass; real model accuracy and
spoken behavior were not validated with a paid Live call.

**Hindi voice speaking form (13 October, final user decision):** The temporary
manual speaking-form selector and subsequent audio-based classifier were both
removed. The child now supplies **Child gender** during fictional family setup:
Female, Male, or an option for neutral phrasing. This family-level field has a
revisioned owner-scoped update for existing families. An assigned child voice
uses female → feminine, male → masculine, or neutral → neutral first-person
Hindi/Hinglish wording; an unset legacy family uses neutral wording. The
standard preset remains feminine regardless of child details. English uses the
selected recorded voice without claims about being the child. No gender is
inferred from audio or a parent recipient label. Old voice profiles can be
reused without re-recording. The short-lived acoustic metadata column, if it
exists in a local vault, is cleared and ignored. No extra paid Google analysis
call is made during voice enrollment. Live instruction adherence and audio
likeness still require a separately authorized listening test.

## 1. The requests and the decisions we reached

The starting problem was that a Mother role-play call answered *“I don't read personal message uploads”* after a chat file had been uploaded. We then discussed natural use of background, repetition, the child-facing **Signals back** area, full conversation history, and automatic email notices.

| Question | Decision reflected in the implementation |
| --- | --- |
| Why did the uploaded chat not affect the answer? | A browser upload/preview is not active call context. The child must select and approve excerpts for the specific fictional recipient. The Live agent must describe that limited reviewed context accurately. |
| Should background be used without the parent explicitly asking? | After an ordinary greeting, a suitable nonsensitive reviewed interest can become a natural opener at most once **per call**. Follow the parent's own topic if they introduce one. |
| How often may HugBack check on a remembered concern? | A reported wellbeing concern can receive at most **two later proactive check-in attempts per episode**, subject to the existing eligibility, cooldown, recovery, and privacy rules. A successful tool claim counts as an attempt even if audio playback is interrupted. |
| What belongs in Signals back? | Dated, recipient-scoped fictional call activity and, after separate standing demo sharing is enabled, a short AI-generated summary of **future** calls, with a date filter. There is no approval after each call. |
| What should trigger an email? | A bounded parent-role self-report of fever or a close bereavement in the current fictional call, after separate standing alert permission. A historical import, AI utterance, or an isolated word does not suffice. |
| What is in the email? | A brief generic update and local portal link. No quote, topic name, health claim, or transcript. The configured test destination belongs to the backend, not a browser field. |

The product architecture remains an **ordinary-phone service**. `/childportal` and `/?demo=parent` are local development/test surfaces, not a released child dashboard, parent app, speaker-verification system, or production consent mechanism.

## 2. Background-chat diagnosis and improvement

### Why the observed answer happened

The `.txt` preview path parses a chat in the browser and can save a temporary copy in browser IndexedDB. Saving that preview does not send the whole chat to the Live agent. For the fictional simulator, the operator must select a recipient, map both speakers, choose short excerpts, and approve the exact selection. Only those reviewed excerpts become the recipient's server-side call context. Mother and Father have independent selections and memory even if they use the same child voice.

The earlier Live wording could also make a blanket denial of chat knowledge. The server's demo context now tells the agent to answer a direct background question using **only the supplied reviewed excerpts**, with correct speaker attribution. If no excerpts are active, it should say that it has no reviewed chat context *for this call*. It must not claim that it read the complete uploaded file.

### Natural conversation behavior

The demo prompt and optional Planner guidance prefer an ordinary greeting and present-day question first. After the parent has answered and the conversation is flowing, one suitable reviewed interest may be brought up as a natural bridge. It should not recite the file, combine all excerpts into one question, present historical information as current, or initiate conversation using old health, distress, financial, or other sensitive details. If the parent asks about background, it answers from the reviewed excerpts; if the parent starts another topic, it follows that topic. This is prompt guidance, so actual Live wording still needs human review and model evaluation.

For the later JohnKeats.AI-inspired tuning request, the user wanted HugBack to decline C++ coding requests and sound less rushed. We inspected the public JohnKeats.AI repository and its local source for the general ideas of a brief role boundary and different pacing for light versus heavy conversation. HugBack keeps its own disclosed-AI identity and parent-companion scope; no Keats persona, text, knowledge base, or calibration pipeline was copied. Its base Live prompt now briefly declines requests to write or debug code while allowing normal conversation about someone's work. It gives more room after a long or emotional parent turn and avoids repetitive fillers. Live's automatic end-of-speech silence changed from a fixed 800 ms to a bounded configurable default of 1000 ms. This is a global turn-detection delay, not a guaranteed adaptive post-turn pause. Offline checks cover the prompt and config; actual spoken compliance and latency remain a separate model/listening test.

The frontend now keeps the parsed preview available after **Save browser copy** and explains the subsequent review/approval action. The parent-call screen warns when the selected recipient has no active reviewed background.

Relevant files: `app/demo/service.py`, `app/workflows/planner.py`; sibling frontend `src/components/BackgroundImports.tsx`, `src/app/page.tsx`, and the existing `src/components/DemoBackgroundReview.tsx`.

## 3. Remembered wellbeing check-ins

The canonical follow-up policy retains its recipient-specific concern lifecycle. This chat added an explicit cap of **two claimed proactive check-in attempts per concern episode**. The counter resets only for a new episode, not simply because another call occurs. Reservation/claim checks still enforce eligibility and existing cooldowns; explicit recovery, suppression, forgetting, and privacy hold can stop a check-in earlier. A newly reported fever is historical context for a later call, not a reason to repeatedly mention it in the current one.

This is a conversation rule, not medical monitoring. The counter records authorized attempts; the system cannot prove that the parent heard a generated question over real telephony.

Relevant files: `app/memory/followups.py`, `app/memory/AGENTS.md`, `tests/test_followups.py`.

## 4. Future fictional-call summaries in Signals back

The simulator has a separate, recipient-scoped **Future call summaries** switch. Enabling it requires the UI to simulate both participants' standing agreement. Future fictional calls process bounded text turns in memory and can save a short generated summary. The child test owner fetches one selected summary through `GET /api/demo/summaries/{recipient_id}/{session_id}`. The endpoint checks family ownership and recipient scope. The UI lists dated calls, filters by call date, and expands a summary, never the raw conversation.

Missing, noisy, or oversized transcription evidence can produce an unavailable summary. Enabling the setting later cannot reconstruct calls whose turns were discarded. An older fictional call with saved text can be converted through an explicit UI action; successful conversion erases those turns. Turning sharing off erases summaries and any legacy saved test text, marks sharing revoked, and invalidates an in-flight writer through the sharing generation. A spoken privacy request also revokes the relevant demo sharing.

Summaries can reflect speech-recognition errors and omit details. No call audio is archived by this path. The feature is for fictional local tests only. Real phone-call history still needs verified family relationships, durable parent consent evidence, phone-to-recipient linking, production storage/read rules, deletion/retention work, and access auditing.

Relevant files: `app/demo/models.py`, `app/demo/routes.py`, `app/demo/store.py`, `app/main.py`, `tests/test_demo_recipients.py`; sibling frontend `src/components/DemoCallHistory.tsx`, `src/components/DemoFamilySetup.tsx`, `src/app/childportal/page.tsx`, `src/lib/demo-api.ts`.

## 5. Automatic topic email notices

The fictional-call backend has an optional Gmail SMTP adapter. It is **off by default**. A notice is considered only after a completed call has eligible summary input, recipient summary and alert sharing are still enabled, and the current parent-role words match the conservative fever or close-loss rules. The detector ignores AI speech and simple negated or third-party mentions. A current no-email/no-alert request revokes alert sharing. At most one topic event is recorded per call; a sent, sending, or pending event for the same recipient and topic suppresses another attempt for 24 hours.

Signals back displays the matched category and email state beside the corresponding dated call: `pending`, `sending`, `sent` (accepted by SMTP), `failed`, `suppressed`, or `not_configured`. SMTP acceptance does **not** prove delivery to an inbox. The email contains a generic update and `http://127.0.0.1:3000/childportal`, which works only on the test computer. It contains no transcript or medical claim. This is not an emergency notification channel.

The backend requires these private **sender** configuration values before attempting SMTP:

```dotenv
HUGBACK_ALERT_EMAIL_ENABLED=TRUE
HUGBACK_ALERT_SMTP_USERNAME=<test Gmail sender>
HUGBACK_ALERT_SMTP_APP_PASSWORD=<private app password>
```

The values belong in the backend's private `.env`, never source control, the frontend, or this document. The landing-page early-access email box was removed. In local SQLite demo mode, Family setup has the only **Child test email** field. An explicit save and expected-recipient checkbox store the selected address with that local family; the public family response shows only a masked hint. The address is never sent to a Firestore test database. A changed/cleared address invalidates pending notices, and the backend rechecks the destination generation before claiming an SMTP send. The checkbox is not real mailbox ownership verification. The operator-only `python -m app.alerts.smoke_test` reports sender readiness without values or sending; `--send --to ADDRESS` explicitly sends one generic probe, without creating a call or Signals back row. Tests mock the provider. A crash can lose a pending process-local send; there is no durable outbox or retry worker yet.

The user entered sender credentials privately in `.env`, and the sender readiness check passed after the obsolete fixed-destination gates were removed. Two live generic probe attempts did **not** send an email: the sandbox had a DNS error; network-permitted retries reached an intercepted SMTP TLS certificate issued by a company gateway, which was not trusted by the public CA bundle. This Python build had no default CA roots, so the sender now uses the maintained `certifi` bundle with TLS verification still enabled. The corporate replacement certificate remains untrusted. No Gmail login or message acceptance occurred. A trusted network or approved system trust configuration is required before retrying live delivery. Do not disable certificate verification.

Relevant files: `app/alerts/policy.py`, `app/alerts/email.py`, `app/alerts/smoke_test.py`, `app/config.py`, `.env.example`, `pyproject.toml`, `app/demo/models.py`, `app/demo/store.py`, `app/demo/routes.py`, `app/main.py`, `tests/test_alerts.py`; sibling frontend `src/components/LandingPage.tsx`, `src/components/DemoFamilySetup.tsx`, `src/components/DemoCallHistory.tsx`, `src/lib/demo-api.ts`. The certifi decision is in the architecture workspace's `docs/OPEN_SOURCE_DECISIONS.md`.

## 6. How the fictional end-to-end path now connects

```text
Child test operator, same browser identity
  → create a fictional family and select Mother/Father separately
  → preview fictional chat locally in the browser
  → map speakers and approve one-action bounded background preparation for that recipient
  → optionally save the expecting child's test email, enable future call summaries and topic-email sharing
  → start a parent role-play call and acknowledge synthetic processing
  → server validates owner, recipient membership/revision and chosen voice
  → Planner selects bounded reviewed references (when enabled)
  → Gemini Live speaks as disclosed AI using selected background
  → Memory Reconciler validates and commits eligible concern observations
  → finalizer saves an eligible short summary and topic/email status
  → child test operator selects that recipient in Signals back
  → dated call and short summary can be opened
```

The separate Quality Critic (when the four-role workflow is enabled) evaluates assistant behavior after the call; its private content-free report does not become a child recap or email. Deterministic server code owns recipient permissions, follow-up claims, transcript commit, and alert status. The Live agent is the only speaking role. Uploaded chat is never automatically fine-tuning data.

### Where information is stored

| Item | Current location / limit |
| --- | --- |
| Full parsed chat preview | Browser IndexedDB, scoped to the local test owner and recipient; not automatically sent to the backend. |
| Reviewed fictional excerpts, recipient metadata, bounded concerns, call status, optional call summary, alert state | Selected synthetic family store: local SQLite by default, loopback Firestore emulator, or a separately authorized isolated named Firestore **test** database. |
| Browser identity | Browser localStorage. A development UUID or Firebase test UID is not proof of a real family relationship. |
| Own-voice test provider key | Separate private local SQLite vault, not the family Firestore test database. |
| Real authorized original imports | Separate trusted Forms/Drive intake design and internal private GCS storage path; the browser preview and fictional simulator do not activate this. |

Selecting Firestore does not move the browser preview, running frontend/backend, or local voice vault to cloud. No existing SQLite family is automatically migrated. No production Firestore writes, cloud resources, paid model checks, phone calls, private imports, or SMTP email were performed for these changes.

## 7. Beginner-friendly test sequence

1. Start the backend and frontend locally, keep the same browser profile and origin, and confirm the synthetic demo is enabled. Use fictional names/content only.
2. In `/childportal` → **Family setup**, create Mother and optionally Father. Choose each recipient explicitly. If you want later short recaps, enable **Future call summaries** before the test call. For a live email test in local SQLite mode, under **Automatic topic email** enter the child's expecting test inbox and click **Save test email for this family**. Then enable the separate **Automatic topic email** permission for the recipient.
3. In **Background**, use `docs/examples/synthetic-agent-chat.txt` or another fictional `.txt`. Map the child and parent senders. **Save browser copy** is only a preview. Select suitable messages and approve the exact reviewed excerpts for Mother. Repeat independently for Father if needed.
4. Start **Test a call as Mother**. Acknowledge fictional Google processing. Ask “What background do you know about me?” and then try a normal greeting. The answer should use only Mother's reviewed context; a greeting may lead to one ordinary historical interest.
5. In a separate fictional test, say “I have a fever today.” End the call and wait for processing. A later Mother call can test a bounded check-in; Father must not inherit the concern. Tests cover the two-attempt cap deterministically without waiting through a real 24-hour cooldown.
6. Return to `/childportal` → **Signals back**, select Mother, refresh, filter by date, and open the completed call. If topic email sharing was enabled, inspect the alert state beside that same call. Without private SMTP configuration, expect `not_configured` and **no email**.
7. To test actual SMTP, first use an operator-controlled test Gmail sender and expecting recipient mailbox, privately set the three sender variables above. Run `.venv/bin/python -m app.alerts.smoke_test` to check readiness without sending; then add `--send --to YOUR_TEST_INBOX` for one generic probe and check the inbox. Restart the backend, save that recipient address in Family setup, make a **new** fictional fever call, and check both the test inbox and that call's Signals back row. The probe is not a call and has no Signals back row. The live probe currently fails TLS verification on this machine's intercepted SMTP network, so inbox delivery was not completed. The exact beginner sequence and status meanings are in `docs/END_TO_END_TESTING.md`.

See `docs/END_TO_END_TESTING.md` for environment profiles, the Firestore emulator and isolated test-database gates, and the offline/paid evaluation commands.

## 8. Verification performed

- Backend: `HUGBACK_WORKFLOW_ENABLED=FALSE .venv/bin/python -m pytest -q` → **283 passed, 1 skipped** on 13 October 2026. The alert suite uses mocked SMTP and a mocked Live WebSocket call, including owner scoping, destination changes, `not_configured`, and failed-delivery statuses. The readiness command confirmed that the private sender settings are ready; it sent **no email**. The separately requested live probe failed TLS verification before Gmail login or message acceptance.
- Frontend: **73 tests passed**; production build/type check passed with the new Family setup field.
- `git diff --check` passed in both repositories.
- No real Gmail SMTP delivery, paid Live/model evaluation, actual Firestore cloud write, PSTN call, or real-family end-to-end enrollment was validated by these checks.

The local private `hugback-test-mother.txt` and `hugback-test-father.txt` files are untracked test data. They are not fixtures for this feature and should not be committed or copied into demonstrations.

## 9. Remaining work before a real family service

1. Connect trusted Forms/Drive intake to verified child and recipient IDs, with real consent from both participants for imported one-to-one history. A browser UUID, phone number, or Form field cannot grant that relationship.
2. Build phone enrollment, carrier integration, speaker/number verification strategy, and an authenticated production child history surface. The local parent role selector is only a persona hint.
3. Obtain and record versioned standing parent consent for future transcript disclosure and topic emails; implement revocation, production Firestore access controls, retention/deletion workers, and audit logs.
4. Choose a production mail provider and add a durable event/outbox, retries, verified child recipient routing, abuse controls, and delivery monitoring. The local Gmail adapter is a test seam, not a dependable urgent-notification system.
5. Run separately authorized model, Live, voice, Firestore/IAM, and real-call evaluations. Prompt guidance and offline mocks do not prove naturalness, transcription accuracy, delivery, or safety.

The architecture source of truth is `Documents/ChatGPT/ELARA/docs/Elara_No_App_Architecture_v4.md`. The sibling frontend's `README.md` and this backend's `docs/END_TO_END_TESTING.md` contain the current simulator instructions.

## 10. Evaluation expansion, 13 October 2026

The previous eval cases were too short to score the conversation failures seen
in testing. `evals/cases.json` now has five grounded Planner cases and nine
Critic cases with **exact** expected finding codes, alongside eight Reconciler
cases. `evals/conversation_scenarios.json` adds multi-turn fictional calls for
later background bridges, one background detail per reply, cross-call topic
rotation, sparse Mumma address, persistent scope boundaries, and quiet requests.
Two additional scenarios check that a fever report is met with support without
an unsupported diagnosis or delivery claim, and that a new person speaking
mid-call is not given Mumma's reviewed background.
Each Live rule has known good and known bad replies; `evals/scoring.py` checks
that the named bad behavior is actually detected before any model run.

`evals/run.py` now lists individual offline rubric outcomes, uses the actual
Live transport for optional text-driven multi-turn scenarios, and supports
explicit `--repeat 1` through `--repeat 5` for paid stability checks. The
existing `--allow-paid-google` gate remains. Reports store case IDs and
outcomes, hashes, model IDs, timing, Git state and limitations; they omit
generated text and provider response bodies. The new beginner reference is
`docs/AI_EVALS_BEGINNER_GUIDE.md`. The backend workflow rules and architecture
eval section were updated to state these limits.

Offline scorer calibration is **not** a claim that Gemini produces the desired
conversation. Paid `models` and `live` suites were not run as part of this
change; they require separate opt-in. Acoustic behavior, speech recognition,
voice consistency, cloud IAM, SMTP and real phone calls remain outside this
eval runner.

Verification for this eval change: the final `--suite offline` run completed
**305 backend tests, one skipped** and reported **46 passing checks, zero
failures/errors**. The added mocked Live transport test exercises both calls of
the background-rotation scenario without contacting Google. `git diff --check`
also passed for the backend and architecture workspaces.

## 11. Quiet and normal voice test flow, 13 October 2026

The existing gentle tone check-in path already used current Gemini Live audio
and a bounded, high-confidence vocal-cue proposal; it had only mocked audio
coverage. The local John Keats example guides its Live agent to match energy
and pace in the prompt; it does not provide a standalone calibrated acoustic
detector to copy. HugBack now states explicitly that microphone loudness alone
must not be called low mood, including for soft cheerful speech.

The fictional call screen now shows a **Microphone input** volume-only bar from
the existing local RMS measurement. It is not stored or treated as emotion.
`scripts/inspect_demo_tone.py` and the owner-scoped `DemoStore.inspect_tone`
method give a trusted local operator a bounded note status after a test call,
without adding a child/browser API or exposing words/audio. The detailed
normal-volume, soft-cheerful, subdued and poor-capture comparison is in
`docs/LOW_VOICE_TESTING.md`. These are manual paid Live checks if actually run;
the offline tests mock provider output and cannot establish acoustic accuracy.
Verification after this change: backend offline eval passed 305 tests (one
skipped) and 46 rubric checks; the focused tone tests passed; frontend typecheck,
81 tests and production build passed. No paid Live acoustic comparison was run.
