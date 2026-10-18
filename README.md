# Hugback backend

## Cloud configuration audit — 18 October 2026

For the operator's reported deployment, see
[`docs/CLOUD_RUN_CONFIGURATION_AUDIT.md`](docs/CLOUD_RUN_CONFIGURATION_AUDIT.md)
and `.env.cloud-run.example`. For the approved hackathon shortcut, a deployment
from this local source directory includes the private, Git-ignored `.env` in the
backend image. A Git-triggered build cannot include that ignored file and falls
back to the secret-free example profile. Explicit remote + public-demo flags
permit verified Firebase anonymous visitors without manual UID approval, while
retaining owner/recipient isolation and an exact HTTPS Origin. Standard and
replicated voice use Firestore state; voice keys require verified backend-only
rules. See the audit for deployment and credential-rotation requirements; this
branch does not itself deploy them.

## Canonical architecture for judging and deployment

Use [docs/HACKATHON_ARCHITECTURE.md](docs/HACKATHON_ARCHITECTURE.md) as the
primary architecture narrative. Cloud Firestore is the canonical deployed state
store; SQLite is an offline test adapter, while IndexedDB is a deliberately local
pre-consent staging boundary rather than a competing source of truth. The running
backend exposes a content-free `GET /api/architecture` manifest used by the
frontend `/architecture` view.

## Four-role workflow + end-to-end evals (12 October 2026)

The synthetic simulator now connects **Planner → existing Live conversation →
Memory Reconciler → Quality Critic**. Canonical recipient-scoped policy remains
the memory authority; the Critic reviews assistant behaviour and never publishes
child recaps. New specialist processing is opt-in with
`HUGBACK_WORKFLOW_ENABLED=TRUE` plus the browser acknowledgement.

Family storage is explicitly selectable: existing SQLite, loopback Firestore
emulator, or an isolated named test Firestore database with matching Firebase
authentication, explicit cloud opt-in and a server-side operator UID allowlist.
This supersedes historical SQLite-only test wording below, **not** the no-app
product direction or production consent/enrollment boundaries.

**Read [the complete end-to-end runbook](docs/END_TO_END_TESTING.md)** for exact
environment profiles, where each item is saved, same-browser Mother/Father
testing, offline/paid eval commands, privacy and failure cases, and activation
gates. Firestore mode now includes the backend-only voice vault; browser previews
remain local. No existing SQLite keys or recordings are silently migrated.
No resource/billing changes, private uploads or paid checks are performed by the
implementation. Post-call work is not yet crash-durable.

For a first-time, step-by-step fictional test of all four roles and their edge
cases, use [the beginner agent test guide](docs/BEGINNER_E2E_AGENT_TESTING.md).
For quiet and normal voice checks, use [the low-voice test guide](docs/LOW_VOICE_TESTING.md).
The eval runner now separates offline regression and scorer calibration from
optional paid structured-model and multi-turn Live scenarios. The Live set
checks conversation pacing, one background detail at a time, later-call rotation,
scope persistence and quiet requests; it does not test microphone audio.

```sh
.venv/bin/python -m evals.run --suite offline --output /tmp/hugback-offline-eval.json
```

## Retained original chat storage (v4.5, 11 October 2026)

The new **internal no-app intake sink** stores exact original WhatsApp exports
in private Google Cloud Storage and recipient-scoped metadata in Firestore.
Originals remain after processing; Mother/Father imports and inactive reviewed
excerpts stay separate. Conditional object creation, hash/generation validation,
transactional reservations and idempotent retries cover partial upload failures.

No new public/browser upload API is mounted. The operator command defaults to
offline validation and makes no Google request:

```sh
.venv/bin/python scripts/import_chat_original.py \
  --manifest docs/examples/synthetic-intake.json \
  --file docs/examples/synthetic-chat.txt
```

Cloud execution is opt-in and needs existing resources/ADC,
`CLOUD_INTAKE_ENABLED`, `FIRESTORE_ENABLED`, `CLOUD_IMPORT_BUCKET`, and separate
execution/storage acknowledgements. No actual environment, resource, billing,
upload or call is enabled by this implementation.

Read [the setup/retention runbook](docs/CLOUD_INTAKE.md) before enabling it.
Automatic Forms/Drive pickup, trusted enrollment, dual-consent activation,
AI extraction, deletion and cloud calling/voice remain separate gates.
Neither upload nor source review activates context. Existing browser demo data
is not migrated; the product remains Forms/Drive intake and ordinary phones.

## Family → adult child → independent recipients (v2, 11 October 2026)

Current product remains **no-app**: Forms/Drive setup and ordinary telephone
calls. Existing browser routes are internal synthetic test tooling, not a
production dashboard or enrollment system. The implemented slice below is local.

- One family and adult-child profile; up to eight recipient profiles with separate
  backgrounds, call metadata, memory/consent, cooldowns, deletion state and leases.
- Explicit recipient selection for every context edit/call; no default recipient.
  Membership is checked against the authenticated local operator's family.
- Standard voice is the initial choice per recipient. One enabled owner-scoped
  child voice can be pinned independently to Mother, Father, or both.
- Old single-parent SQLite state migrates transactionally to **Existing parent**.
  IDs/history/active leases are retained, not copied to Mother/Father. Its voice
  defaults to standard and requires an explicit new custom assignment.
- Raw local previews are namespaced by browser owner + recipient. Legacy unassigned
  previews stay with the legacy recipient, not newly created recipients.
- No voice-based caller recognition, automatic household switching, production
  phone linking, or recap sharing. End a call before another person takes over.


## Live conversation scope and pacing

HugBack's Live conversation is scoped to companionship. Requests for task
outputs, facts, explanations, recommendations, or professional guidance receive
a short spoken boundary across coding, politics, travel, shopping, homework and
similar domains. Personal stories mentioning those subjects remain conversation;
immediate safety concerns receive a supportive safety response. This is a Live
prompt and post-call Critic check, not a deterministic pre-speech filter for
streamed native audio. The default Live end-of-speech
silence is 1300 ms (`HUGBACK_END_OF_SPEECH_SILENCE_MS`, accepted range 700–1600);
raising it gives the caller more room between phrases but increases response
latency. The native-audio SDK's SpeechConfig has no speaking-rate field in the
installed version, so spoken tempo and pauses inside the model's reply remain
prompt guidance rather than a guaranteed playback speed. John Keats uses the
same 1000 ms end-of-speech setting; its additional silence guidance is in its
persona prompt. HugBack now asks for natural space between short thoughts and
avoids seeded hobby examples. Test with synthetic calls in short, long and
emotional exchanges before judging the perceived pace; no paid listening test
was run while changing this setting.

## Child portal → Google replicated TTS (11 October 2026)

The operator reports that the friend's paid Tier 1 Voices/TTS flow works and
explicitly requested portal integration. This is **local browser testing**, not
telephone enrollment, production family authorization or independently verified
speaker likeness. No real recordings or paid calls were used to verify this patch.

1. Keep `HUGBACK_AUTH_MODE=development`, `HUGBACK_LIVE_VOICE_MODE=preset` and a
   configured backend Gemini API key. Set `HUGBACK_REPLICATED_TTS_ENABLED=True` to
   expose upload capability. Keep `LOCAL_DEMO_ENABLED=True` for the parent demo.
   No new frontend key, sign-in form, Firebase resource or hosted processor.
2. In `/childportal` → **Voice setup**, choose your own adult-speaker sample
   (10–30s) and separate spoken consent (2–30s), each under 10 MB. The browser
   converts supported formats to mono PCM16 24kHz WAV. Server validation bounds
   decoded files to 2 MB and validates their complete WAV frames.
3. Explicitly acknowledge adult own-voice, Google processing and possible billing,
   then **Upload & create voice**. No upload on file selection/mount/call start.
   The backend sends both recordings to Google Voices with `store=False`, no
   creation model override, one transmission, bounded timeout and no automatic
   enrollment retry. `PERMISSION_DENIED` is not automatically diagnosed as a
   billing problem. Google acceptance is not proof of likeness/identity.
   No separate gender or speaking-form analysis is made from the recording.
   If enrollment fails, refresh **Voice setup** status before another upload.
   The server reports the first Google HTTP status when available without
   exposing its response body: 401/403 suggests checking the backend key's
   project access or feature eligibility; 429 points to quota; 5xx points to
   provider availability. An unknown outcome or local vault save error is shown
   separately. The old generic `RuntimeError` log alone cannot identify which
   of these caused an earlier failure. A new attempt may be billable, so it is
   always a deliberate user action.
4. Enrollment returns metadata, never a provider key. Choose **Enable child
   voice**, then select a recipient in **Family setup** and **Assign child voice**.
   Repeat for each intended recipient; enabling alone does not assign it. Both
   Mother and Father can use the same profile without sharing context or memory.
   Expiry, disablement, removal or replacement blocks stale assignments; reassign
   or choose **Use standard voice** for that recipient. Changes apply to **new**
   calls; end an active call first.
5. `/?demo=parent&recipient=<id>` resolves the voice from the browser operator
   before validating the selected recipient's membership, revision and voice.
   Only then does it resolve that recipient's memory scope. The WebSocket accepts an opaque
   `voiceProfileId`, never raw `voiceKey`. Gemini Live handles conversation and
   uses the family-level child gender entered in **Family setup** for
   Hindi/Hinglish first-person wording. English keeps the selected audio voice.
   Standard calls use the feminine preset and feminine wording. An existing
   custom profile can be reused after saving child details; no new recording is
   needed. If child gender is unset, custom-voice wording stays neutral.
   transcription; its preset audio is discarded, and only Google streaming TTS
   audio using that profile reaches playback. The key is NOT a Live voice ID.
   One ordered emitter with bounded one-phrase synthesis lookahead spans turns,
   cancels interrupted speech, closes SSE/client resources, and checkpoints
   emitted TTS off the audio path. Failures stop
   the call rather than mix preset/custom voices. In the fictional simulator,
   HugBack opens by name and answers direct AI-identity questions honestly.

   The first phrase can start at an earlier clause/word boundary. Lookahead
   may spend synthesis on interrupted audio; set `HUGBACK_TTS_LOOKAHEAD=0` for
   serial requests. Existing voice keys are reused, not recreated per reply.
   See [latency settings, diagnostics and offline checks](docs/END_TO_END_TESTING.md#replicated-voice-reducing-application-latency).
   Native Live latency parity and actual provider speed remain unmeasured.

**Storage:** source audio remains transient browser/backend memory and is sent
to Google only after the adult own-voice, spoken-consent and Google processing/
billing acknowledgements. `store=False` is not a promise about all provider
processing/retention. With `HUGBACK_DEMO_STORE=firestore`, BOTH synthetic family
state and temporary child-voice keys use the same configured named Firestore
database (`hugback-synthetic` in the shared project). Standard Google voice needs
no custom key. The separate `hugback_private_voice_profiles` collection stores
only the temporary key, owner-hashed profile metadata and enrollment lease;
no recordings or transcripts. Browsers receive metadata only, never provider keys.

Before enabling voice operations, verify the named database has deny-all browser
rules (`firestore.synthetic.rules`) and appropriate backend IAM, then set
`HUGBACK_FIRESTORE_VOICE_RULES_CONFIRMED=TRUE`. This flag records an operator
verification, not an automatic rules audit. Keep IAM narrowly scoped: server SDKs
bypass Firebase rules. Firestore provides managed encryption at rest, not a separate
application encryption layer; authorized backend/database administrators can read
keys. Do not put permissive authenticated-user rules on this database.

Firestore transactions serialize enrollment/replacement/removal per owner across
instances. A 120-second lease fences late provider responses; the provider upload
has a 55-second timeout and no automatic retry. New/replacement profiles are
disabled until explicitly enabled and assigned per recipient. Keys are unusable
after the earlier of provider expiry or seven days. Expired keys are cleared on
successful access; there is no scheduled retention/purge job. Metadata remains to
prevent silent standard-voice fallback. **Remove voice** erases the saved key and
profile, but does not revoke Google's key, erase provider retention, or stop a
call already using it. End active calls first.

SQLite is retained only as an explicitly selected offline test adapter. Firestore
mode never opens it and never falls back if cloud storage fails. Existing local
keys/recordings are not copied or deleted automatically. Browser drafts and auth
tokens remain in browser storage; moving keys does not upload raw chat previews.
Use the same Firebase browser identity to retain access. Recovery, real-family
identity/consent, provider likeness/entitlement and paid latency checks remain
separate gates. Both voices are supported by code; that is not a deployment claim.

Offline checks: `python -m unittest discover -s tests -q` (backend virtualenv),
`npm test`, `npm run typecheck`, isolated frontend production build. Fixtures are
synthetic and all provider I/O is mocked. Never use real family material in tests.

## Local hackathon demo: steps 1–5

The user approved a **synthetic-only** local family simulator. It is separate
from all production enrollment, storage and sharing. No sign-in UI is added.

Configuration: set `LOCAL_DEMO_ENABLED=TRUE`, `HUGBACK_AUTH_MODE=development`,
`HUGBACK_LIVE_VOICE_MODE=preset` locally. Keep `MEMORY_ENABLED`, `FIRESTORE_ENABLED`
and `FOLLOWUPS_ENABLED` false for the demo. Existing Google credentials/model
configuration is reused **only when an operator starts a call**. Structured
post-call extraction uses `FOLLOWUP_EXTRACTION_MODEL`; its availability,
entitlements and real output quality have not been validated by offline tests.
Never run the simulator for private/real family data or expose it publicly.

1. In the internal `/childportal` simulator, create a fictional family and first
   recipient. Add Mother/Father separately, each with simulated setup consent and
   their own optional wellbeing-memory consent. Select whom you are preparing for.
2. Parse a fictional chat locally, map both participants, and approve preparing
   bounded context as both simulated participants. One click considers every
   parent-authored message and sends up to 20 parent background excerpts plus
   up to four short, attributed child replies for broad conversational style.
   There is no message-by-message
   selection, but long exports are not retained or fully recalled in calls.
   This is deterministic context preparation, not AI fact extraction.
3. Use **Test a call as [recipient]**. The URL includes the recipient hint;
   acknowledge fictional role-play/Google processing before starting a call.
4. `/ws` accepts `demoParent: true` only under the local gates, with required
   `demoRecipientId` and strict integer `demoRecipientRevision`. It validates
   owner membership, revision, idle lease and the exact pinned `voiceProfileId`
   (omitted for standard). Missing, foreign or stale selectors fail before Google.
   Calls always get a new server session ID. This is not real-human verification.
5. Before Gemini connects, the server loads the reviewed historical context and
   optional canonical wellbeing follow-ups for that parent. After the call,
   consented Google structured extraction proposes source-backed wellbeing
   records; deterministic validators authorize writes. A failed update is shown
   as `memory_failed`, never fabricated as success. The next call waits while the
   previous call for that recipient is active or processing.

Persistence: `.local-demo/hugback.sqlite3` (gitignored, owner-only file permissions;
override via `LOCAL_DEMO_DB_PATH`). Distinct server-generated family, child and
parent IDs survive browser refresh and backend restart. The browser credential
still lives in localStorage; clearing it loses access and has no recovery.
The raw parsed preview remains in browser IndexedDB, not SQLite or Firebase.
Backend records hold approved excerpts, at most 20 call records per recipient and
bounded canonical wellbeing concerns. Full text is retained only for future
fictional calls after separate standing history sharing; audio and recaps are not
stored by that path. See `docs/CHAT_WORK_RECORD_2026-10-13.md`.
Production Firestore/Memory Bank/Cloud Tasks are bypassed for demo calls even if
their flags are accidentally on. Demo families expire after seven days; physical
cleanup occurs on next DB access, not through a guaranteed background worker.
Concern retention defaults to 72 hours; a newly reported concern is eligible on
the next call, but selection then applies a 24-hour cooldown and one-claim limit.
Only fever, sleep, appetite, energy and physical comfort are extracted in this
slice. This is not unrestricted autobiographical memory or model fine-tuning.

### Consent-gated conversation signals

Recipient creation now offers a separate simulated consent for a short
AI-estimated call signal. This permission is independent from cross-call memory.
When enabled, Gemini Live may silently propose one bounded category (`upbeat`,
`calm`, `neutral`, `lower_energy`, `tense`, or `unclear`) with confidence and a
fixed list of evidence types. The model never supplies the recipient ID and its
proposal never writes directly to storage.

The server rechecks the active call, recipient, consent generation and schema.
`low` confidence and `unclear` are abstentions. A publishable signal is rendered
from server-owned text, retained locally for 72 hours, capped at ten per
recipient, and shown only in that selected recipient's child-portal card. Raw
audio, transcripts and model reasoning are not stored by this path. An in-call
"don't share/tell" request clears existing signals and revokes this sharing
without changing conversational-memory consent. Signals are explicitly labeled
AI-estimated and non-medical; they never create an emergency alert.

Routes: `GET/POST /api/demo/family`, `POST /api/demo/recipients`,
`PUT /api/demo/recipient-voice`, `PUT /api/demo/background`,
`POST /api/demo/background/clear`, `PUT /api/demo/wellbeing-sharing`. Family
responses have `schemaVersion: 2` and
a `recipients` array; private canonical memory/leases are not returned. Background
and voice mutations require `recipientId` and the recipient's current `revision`. Mutations and demo sockets require an
allowlisted loopback Origin and the actual loopback network peer; forwarded
headers cannot satisfy that check. Reviews use optimistic revisions and cannot
replace context mid-call. Consent simulation never creates a verified grant.
An operator's synthetic-data checkbox cannot prove a file is fictional.

Call cap: ten minutes. SQLite leases serialize calls per recipient and expire after twelve
minutes if the process dies. Post-call work is bounded and shielded from browser
disconnect cancellation, but is **not a durable outbox** across process shutdown.
An interrupted server may lose the pending extraction; stale leases display
`interrupted`. Do not restart during an active demo.

Real-family identity, verified enrollment, unrestricted cloud uploads and durable
retry recovery remain outside this simulator. The hosted judge flow can email the
already-bounded generated call summary after it is stored. Family setup saves one
owner-scoped notification inbox with the authenticated family in SQLite or the
deny-all named Firestore database; responses return only a masked hint. Sender
credentials remain backend secrets. Changing or clearing the address invalidates
pending sends. Raw turns and imported excerpts are never emailed.
For a local sender check, run `.venv/bin/python -m app.alerts.smoke_test`
from this repository. It prints only readiness flags and sends nothing. After
privately configuring a sender, add `--send --to ADDRESS` for one
generic probe to an expecting test inbox; then make a new fictional call to test topic detection and the
Signals back status. See `docs/END_TO_END_TESTING.md` for the exact steps.
Existing gated summary reads are unchanged.
Tests use temporary DBs and fake Google sessions, including fever → next-call
follow-up → cooldown and explicit resolution. No real Google call is a test
prerequisite.

## Narrow child portal — 11 October 2026

The user explicitly approved `/childportal` in the existing frontend, with no
sign-in screen. It reuses Firebase anonymous REST identity when configured; the
currently running local setup was checked and uses `development`, not Firebase.
Frontend chat previews remain browser-local; the explicit voice upload flow is described above. No private data or calls
were sent as part of this change.

New read-only routes: `GET /api/portal/status`, `GET /api/portal/summaries`.
They use the same verified Firebase bearer token as other HTTP APIs. In
development, the peer must be loopback and no cloud mailbox is read, even if
feature flags are enabled. Unknown authentication modes fail closed.

`PORTAL_SHARING_ENABLED` defaults FALSE and additionally requires Firestore.
The single bounded `child_portal_mailboxes/{sha256(child_uid)}` document contains
a trusted relationship and at most 50 approved updates. Relationship fields:
`child_uid`, `parent_id`, `status=verified`, integer `generation`, aware
`verified_at`/`expires_at`. Update fields: `id`, matching child/parent IDs,
`relationship_generation`, `status=approved`, `approval_source=verified_parent`,
`approved_text`, SHA-256 `approved_text_sha256`, aware `call_ended_at`,
`approved_at`, `expires_at`. The API emits only this approved text and safe
metadata, never arbitrary document fields.

This is a **reader contract**, not an active sharing pipeline. Trusted phone
enrollment, exact-content parent approval/summary production, Firestore client
write-denial rules/IAM tests, durable processing, email delivery, identity
recovery and physical retention workers remain release gates. A local or child
checkbox cannot create a verified relationship. See `app/portal/AGENTS.md`.
No cloud resources, billing or provider settings were enabled. Real Firestore
integration is untested; adapter tests mock its I/O.

The frontend call test now queries authenticated portal capabilities before
reading any optional voice recordings. Standard preset calls never upload those
recordings. Voice setup distinguishes created, selected, expired and unavailable states.

FastAPI broker for Gemini Live audio with authenticated, user-scoped long-term
memory.

## Local development

1. Copy `.env.example` to `.env` and configure Gemini authentication.
2. Leave `HUGBACK_AUTH_MODE=development`, `MEMORY_ENABLED=FALSE`, and
   `FIRESTORE_ENABLED=FALSE` for a memory-free local call.
3. Install dependencies and run the service:

   ```bash
   pip install -e .
   ./run.sh
   ```

The frontend stores a random development user ID in the browser. Development
IDs provide continuity, not security, and must not be enabled in production.

## Voice consistency — 11 October 2026

This is configuration/prompt hardening, **not model weight fine-tuning** and not
proof that audible speaker drift is fixed. The current Google Developer API
[fine-tuning guide](https://ai.google.dev/gemini-api/docs/model-tuning) does not
offer fine-tuning. Cloud tuning availability for other models does not establish
support for this Live model or an acoustic-identity guarantee.

### Deterministic voice selection

- The pulled replicated-voice Voices API/TTS path is retained separately behind
  `HUGBACK_REPLICATED_TTS_ENABLED=FALSE` by default. It is **not** a Live voice ID
  or part of the local demo. Enabling it requires an explicit provider,
  recording-consent, identity, and privacy review; neither the endpoint nor a
  browser `voiceKey` activates it while the gate is off. An API response alone
  does not establish speaker likeness.
- `HUGBACK_LIVE_VOICE_MODE=preset` is the ordinary-call default. It uses
  `HUGBACK_VOICE_NAME` (currently `Aoede`) for the whole upstream session.
- A saved browser sample/consent payload is **rejected before Google**, not
  allowed to override the preset or silently ignored. Existing test clients with
  a saved voice profile must remove it before making a preset call.
- `HUGBACK_LIVE_VOICE_MODE=experimental-inline` is for explicitly authorized
  operator research only, not an approved MVP feature. Every call must supply
  both recordings; missing/invalid inputs stop the call instead of falling back.
  This mode transmits recordings during Live setup; validate adult-speaker
  consent, data terms, provider access, and billing authorization before using it.
- Experimental setup must return a nonempty voice consent signature before
  `ready` or caller audio forwarding. Missing evidence stops the call without a
  preset retry. Acknowledged consent still does **not** verify speaker likeness.
- TTS/managed voice IDs are not accepted by the ordinary Live config builder.
  The separate compatibility scripts remain isolated from this policy.
- Gemini model calls use only the configured server-side API key. There is no
  alternate runtime model-provider switch or silent endpoint fallback.

The `ready` event now reports `model`, `voiceName`, `voiceStatus`, and `sessionId`.
For preset mode, status is `preset_configured`; for experimental inline mode it is
`consent_acknowledged_likeness_unverified`, never a successful-cloning claim.
Metadata-only connection logs identify the selected model/mode/preset. Do not
log recordings, consent signatures, model output, or voice-key fingerprints.
There is no automatic model/voice fallback or reconnect in the current broker.

The prompt now requests one named HugBack speaker, consistent timbre across turns
and language changes, no imitation/character voices, short replies, and calm
delivery. This follows Google's
[Live prompting guidance](https://ai.google.dev/gemini-api/docs/live-api/best-practices);
it is a mitigation to evaluate, not an enforced acoustic lock. Temperature,
thinking settings, model selection, and the private `.env` were not changed.

### Findings and remaining validation

Before this change, browser enrollment could silently select the experimental
inline path instead of the preset, and `ready` called it `replicated` merely
because samples had been supplied. Neither proves that this caused the reported
within-call voice change. Local mocks now verify that multiple turns and an
interruption reuse one upstream connection and one voice configuration.

The legacy browser playback audit also reproduced an independent ring-buffer
underrun defect: after wrap-around an empty buffer emits an old sample instead
of silence. This can cause playback artifacts; it is not evidence of a different
model speaker. The browser also sends `turn_complete` on edge barge-in, which
interrupts generation on the
[configured model](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-live),
and does not validate PCM rates.
The original voice investigation made no frontend changes. The subsequently
approved child-only portal and local voice-routing changes are described above;
the parent remains phone-only.
Do not reuse those legacy audio behaviors in the carrier adapter.

Before any authorized listening test, record whether the symptom is within one
session or across calls and whether the intended voice is preset or experimental.
Use synthetic conversation content, not family history:

1. Baseline: one fixed model and preset, memory disabled, ordinary English
   questions, 20 short turns. Observe voice identity, pace, and response latency.
2. Repeat with Hindi/Hinglish language changes, quoted sentences, interruptions,
   and pauses. Keep the selected voice unchanged.
3. Repeat across three new sessions; compare `ready` metadata to distinguish
   application selection from acoustic drift. Also check later turns in a longer
   call, subject to the existing session-duration/provider limits.
4. Separate speaker-identity changes from accent, emotion, clipping, or playback
   artifacts. A human listening review is required; pitch alone cannot certify
   speaker identity.
5. Only if drift persists under identical configuration, run an authorized
   provider/model A/B test or evaluate a separate Google TTS output path. Neither
   is implemented or approved by this patch.

No live requests, recording uploads, paid calls, or training runs were performed
for this investigation. The automated tests establish routing and safety
invariants, not real-world voice consistency or latency improvements.

### Troubleshooting startup after a pull

If the browser reports `Unable to connect ... :8000/ws`, check the backend
terminal first. An import failure prevents Uvicorn from serving HTTP or WebSockets.
Use the same virtual environment to check startup and the regression tests:

```bash
.venv/bin/python -c "import app.main; print('Backend imports successfully')"
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Then check `http://127.0.0.1:8000/health`. The latest WebSocket protocol requires
the frontend to send an `authenticate` message before the backend connects to
Gemini. A bare socket connection is not a completed AI session.

The `app/voice/` Python package must be included in Git. Private recordings belong
outside source control; the root `/Voice/` directory remains ignored. Do not use
an unanchored `Voice/` ignore rule: it hides `app/voice/` on case-insensitive Macs.
The inline WAV validator only checks the client's recording format; it does not
prove consent, speaker identity, or custom-voice access at Google. Use the preset
voice for the initial connectivity check.

## Private recordings: offline-first voice compatibility check

The reference WAV is input for voice replication. The consent WAV is a separate
authorization recording; its filename or audio format does not prove the speaker
gave valid consent. A previously generated result WAV is **output for comparison**,
never a replacement for the reference or consent.

Keep inputs outside the repository. The optional settings
`HUGBACK_VOICE_REFERENCE_PATH`, `HUGBACK_VOICE_CONSENT_PATH`, and
`HUGBACK_VOICE_TEST_OUTPUT_PATH` supply paths to the isolated script only. Set them
in your private `.env`, or pass `--sample`, `--consent`, and `--output`. Do not
point output at an existing result; the script refuses to overwrite it.

```bash
# Local checks only. No Google connection, upload, output file, or voice training.
.venv/bin/python scripts/check_live_voice_replication.py

# Preview the first 20 seconds in memory and build the Cloud PCM payload locally.
# The input files are not modified.
.venv/bin/python scripts/check_live_voice_replication.py \
  --reference-seconds 20 --wire-format cloud-pcm
```

There are two explicitly different experimental wire formats:

- `cloud-pcm` follows the [Cloud Live custom-voice guide](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/live-api/configure-language-voice#use-a-custom-voice):
  a 10–20 second PCM s16le reference. The script extracts raw samples from the WAV
  container and declares `audio/pcm;rate=24000`. A live test uses the configured
  Cloud project/region with ADC, not the AI Studio API key. The consent recording
  is validated locally but is not transmitted by this documented sample-only
  payload; confirm the project's actual consent requirements with Google.
- `sdk-wav` retains the installed SDK's WAV-plus-consent experiment. It sends
  both recordings using the existing client authentication selection. That SDK
  schema differs from the Cloud guide; schema construction is **not** proof of
  provider compatibility or a successful consent check.

For an explicitly authorized provider test, both `--run-live` and
`--confirm-consent` are required, plus an explicit wire format for inline mode.
These flags authorize sending the selected recording data to Google and possible
usage charges. Resolve account access, data terms, adult-speaker consent, endpoint,
and region requirements first. Do not assume Google One grants API entitlement.
The older `--mode voice-key` path is a separate TTS experiment, not evidence that
TTS voice keys work in Live, and is also offline unless explicitly opted in.

Configuring these file paths does **not** change the voice of normal calls or
silently upload a shared speaker's recording for every user. Experimental caller
recordings require the explicit server mode described above and an authenticated
WebSocket envelope. A
production server-side voice-profile feature requires scoped authorization and
revocation; this local script is not that feature.

### Voice experiment outcome — 11 October 2026

The authorized SDK-WAV/Developer-API Live probe returned audio, but the operator
reported that the output did not resemble the reference speaker. **Speaker-likeness
validation failed.** Connection success and receipt of audio are not evidence that
a custom voice was applied; no custom voice should be promoted to ordinary calls
on that basis.

An offline test through the installed SDK's actual WebSocket serialization path
confirms that both sample and consent fields survive and that no preset voice is
added. It does not prove how the server processed those fields. The earlier probe
did not inspect the setup consent-verification signature, so its presence or absence
in that run is unknown.

The SDK-WAV probe now conservatively requires a nonempty
`setup_complete.voice_consent_signature.signature` before requesting speech.
That field is described by the installed SDK as evidence of verified consent,
**not** proof of voice likeness. Missing evidence stops the probe without an
output; it does not diagnose project entitlement or prove a server fallback.
The signature is never logged or persisted. The same conservative gate is now
also used by the explicitly enabled experimental-inline broker mode; ordinary
calls default to the configured preset and cannot upload enrollment recordings.

The documented [Developer API voice-replication flow](https://ai.google.dev/gemini-api/docs/voice-replication)
creates a replicated voice through the Voices API and uses it in TTS synthesis.
That is distinct from the restricted Cloud Live inline-reference example. Testing
that separate TTS route, its data-handling terms, and its voice likeness remains a
next-step gate, not a tested fix or permission to upload another recording.

### Separate Voices API → TTS probe

`scripts/check_tts_voice_replication.py` tests the documented Developer API
enrollment/synthesis flow independently of Live. It reads `GEMINI_API_KEY` from
the backend configuration, explicitly uses Developer API `v1beta`, and does not
use the browser's signed-in account or another model-provider fallback. The key itself
does not reveal its owner, billing tier, or model entitlement.

```bash
# Offline validation, no cloud request:
.venv/bin/python scripts/check_tts_voice_replication.py \
  --sample /absolute/private/reference.wav \
  --consent /absolute/private/consent.wav \
  --output /absolute/private/new-tts-preview.wav
```

Only with adult-speaker upload consent and authorization to charge the key
owner's project, add `--run-live --confirm-consent-and-billing`. A real probe:

1. Requests a replicated voice with `voices.create(store=False)`.
2. Requires a returned client-managed `voicekey_...`, kept in memory only.
3. Uses that exact key in one `gemini-3.8-flash-tts` synthesis request with
   `interactions.create(store=False)`. It never invokes Live or a preset fallback.
4. Validates the short WAV output and saves a new private file for human review.

Both requests disable automatic retries and have bounded timeouts. `store=False`
avoids a persistent managed voice and retrievable interaction; it is not a blanket
zero-retention promise for provider processing or logs. The probe does not store
the voice key, alter ordinary calls, or establish voice likeness from API success.
Account access and actual speaker likeness remain unverified until a real test
and operator listening review. Full conversational integration is a later step.

## Canonical follow-up pilot — 11 October 2026

The local implementation separates **what was reported** from **permission to
ask again**. `FOLLOWUPS_ENABLED` defaults to `FALSE`; this patch does not enable
Firestore, enroll a parent, upload a transcript, or create cloud resources.

### Current behavior when explicitly enabled and consented

1. A trusted enrollment adapter must map the verified parent to the server owner
   scope and call `FollowupCoordinator.record_verified_consent` with a consent
   version, evidence/source reference and IANA timezone. Consent here must cover
   retention of direct-call wellbeing reports; voice consent is not sufficient.
   There is deliberately no public/Live tool that grants this consent.
2. At call start, one Firestore transaction expires unusable records and reserves
   at most one eligible follow-up. A **24-hour** global/per-topic cooldown limits
   rapid reconnects and concurrent calls. This is a conversational default, not a
   clinical schedule. A reservation starts cooldown even if the call is abandoned,
   conservatively preferring a missed prompt to repeated questions.
3. The bounded context card exposes policy, not a hidden list of health details.
   `claim_followup` rechecks consent, generation, expiry, suppression and current
   processing state before releasing one report. Duplicate claims are denied.
   An explicit mention of that topic by the parent also closes that call's
   proactive opportunity; prompt rules handle subtler topic changes.
4. After disconnect, a bounded Google structured-output request proposes
   observations from timestamped text. Only exact USER-source evidence with valid
   turn IDs, current consent generation and fresh timestamps may be committed.
   Requests and commits are parent-scoped; delayed/duplicate results cannot
   overwrite newer reports. The transcript is held in process memory only and is
   **not persisted** by this path. Provider data-handling terms still apply.
5. Canonical records contain a topic, user evidence, source session/turn, report
   times, lifecycle state, eligibility and expiry. This first slice supports
   `fever`, `sleep`, `appetite`, `energy`, and `physical_comfort`; it is not a
   general autobiographical memory implementation.

Example: a self-reported fever becomes `open`; “a little better” becomes
`improved`, not `resolved`. An explicit recovery becomes `resolved`, which is not
selected again. Silence or changing the topic does not resolve it. An explicit
new report after recovery can start a new episode. No diagnosis is inferred.

`control_followup` accepts only grounded current-user privacy instructions:
stop asking, forget a topic, or forget all. Suppression/forget removes the
retained quote and leaves a content-free topic suppression marker; the backend
does not automatically re-enable it. Generation changes invalidate pending
writes and plans. Unhandled recognized privacy wording places memory on a
**privacy hold** without sending that transcript to extraction. A trusted
clarification/enrollment flow is required to clear the hold; that flow is not
implemented here. The narrow English/Hindi/Hinglish checks are conservative,
not a guarantee of understanding every spoken privacy request.

### Operational and privacy boundaries

- Raw audio/transcripts are never stored by the canonical path. Only bounded
  source evidence is retained. Text still goes to the configured Google endpoint
  during authorized extraction; this is not a zero-retention provider claim.
- **72 hours** is the default concern eligibility/retention target. Expired
  content is excluded and physically removed on the next begin/inspect/finish
  operation. A scheduled purge for dormant records is a remaining deployment
  gate; there is no claim of exact-time physical deletion today.
- Planned, generated-after-claim, and interrupted timestamps are separate.
  “Generated” does not verify that the question was actually spoken, delivered,
  heard, or answered. There is no playback acknowledgement from a carrier yet.
- `ready.memoryStatus` reports `ready`, `disabled`, `pending`, or `unavailable`
  for the canonical path. A call starting during extraction receives no stale
  follow-up. It does not automatically refresh its plan when processing finishes.
- Canonical mode **bypasses legacy Memory Bank retrieval, tools, generation and
  raw session storage in the call broker**. Do not switch back to unfiltered
  legacy memories after suppression/deletion without a canonical migration.
- The authenticated inspect API shows canonical concerns; the delete API first
  revokes/tombstones canonical state, then purges the legacy stores. There is no
  general-purpose consent or retention-management frontend. If Firestore is
  disabled/unavailable, deletion returns an error rather than pretending that
  configuration changes erased previously stored records.
- Transactions implement selection/write isolation following the
  [Firestore transaction API](https://docs.cloud.google.com/firestore/native/docs/manage-data/transactions).
  Extraction uses the existing Google SDK and
  [Generate Content structured output](https://ai.google.dev/gemini-api/docs/generate-content/structured-output).
  No dependency or non-Google processor was added.

### Still gated before real use

The local suite verifies lifecycle rules, provider-request construction, broker
routing, and an adapter contract with mocks. It does **not** verify real
Firestore transactions, semantic extraction accuracy, actual speech behavior,
or model/region entitlement. The Firestore SDK is not installed in the inspected
local virtual environment. The trusted parent enrollment/consent adapter remains
to be connected; a browser development UUID is not verified parent identity.

Post-call extraction is bounded/awaited, but there is **no durable retry outbox**
for this pilot. A crash or provider failure can lose that call's memory update.
The pending lease times out rather than inventing an update. Production needs a
consented minimal-data outbox, worker retries, prompt-compliance evaluations,
privacy-language tests and scheduled expiry cleanup before activation.
Do not simply flip flags or run the old Memory Bank setup script as a substitute.

Offline checks:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_followup*.py' -v
.venv/bin/python -m unittest discover -s tests -q
```

## Legacy semantic memory setup (not the canonical follow-up pilot)

The steps below configure the earlier semantic-memory experiment. They do not
provide the canonical consent, cooldown, lifecycle or privacy gates above.
Do not use this path for production wellbeing memory.

1. Enable the Agent Platform, Firestore, Cloud Tasks, and Firebase Authentication
   APIs in the Google Cloud project.
2. Enable Anonymous Authentication in Firebase Console.
3. Authenticate locally with Application Default Credentials.
4. Create the configured Memory Bank once:

   ```bash
   python scripts/create_memory_bank.py
   ```

5. Copy its printed resource name into `MEMORY_BANK_NAME`, then set:

   ```dotenv
   MEMORY_ENABLED=TRUE
   FIRESTORE_ENABLED=TRUE
   HUGBACK_AUTH_MODE=firebase
   FIREBASE_PROJECT_ID=your-project-id
   ```

6. Set `NEXT_PUBLIC_FIREBASE_API_KEY` in the frontend `.env.local` file.

The Memory Bank setup uses `gemini-embedding-001` for multilingual semantic
retrieval, a structured `hugback-care-profile`, memory revisions, and TTL refresh
when a fact is reinforced.

## Production post-call processing

Create a Cloud Tasks queue and configure the deployed backend:

```dotenv
MEMORY_PROCESSING_MODE=cloud_tasks
CLOUD_TASKS_LOCATION=us-central1
CLOUD_TASKS_QUEUE=hugback-memory
MEMORY_PROCESSOR_URL=https://YOUR_SERVICE/internal/memory/process
CLOUD_TASKS_SERVICE_ACCOUNT=YOUR_TASK_INVOKER_SERVICE_ACCOUNT
```

The task service account's OIDC identity is verified by the endpoint. For local
task testing, use `MEMORY_TASK_SECRET` instead. Never deploy with development
authentication.

## Privacy controls

- `GET /api/memories` returns the authenticated user's structured profiles and
  natural-language facts.
- `DELETE /api/memories` purges that user's Memory Bank scope and Firestore
  transcripts.

With Firebase authentication, send `Authorization: Bearer FIREBASE_ID_TOKEN`.
For local development only, send `X-Hugback-Development-User: BROWSER_USER_ID`.

## Tests

```bash
python -m unittest discover -s tests -v
```
