# Hugback frontend

Current product is **no-app**: child setup through Forms/Drive, parent calls on an
ordinary phone. Existing `/childportal` and `/` are internal local prototype/test
surfaces, not a product dashboard rollout. No hosting or deployment is authorized.

## Conversation history (13 October 2026)

For future **fictional** simulator calls, Family setup offers a separate
simulated standing permission for short AI call summaries. Once enabled,
Signals back shows the selected recipient's dated calls and available summaries,
never new raw turns; no per-call approval is needed. Enabling it after a call
cannot recover discarded text. Turning it off erases saved summaries and any
legacy test text. Local SQLite or an explicitly selected isolated Firestore
test store holds these records.
Real phone-call history is not connected: verified parent/child enrollment,
standing parent consent and production Firestore access are still required.

The fictional simulator now also offers a separate standing permission for
brief **automatic topic emails** after a parent-role self-report of fever or a
close loss. Signals back shows the topic and whether the email was sent,
suppressed, failed or unconfigured beside the call history. In local SQLite
demo mode, the child enters the expected test inbox only in Family setup; the
landing page has no email form. The backend stores that address with this local
demo family. SMTP sender credentials stay in the backend's private `.env`.
SMTP is off by default, sends no transcript and is not an emergency
channel. See the backend test guide for private Gmail SMTP setup.

## Four-role workflow and Firestore test mode (12 October 2026)

The existing simulator now supports the backend's opt-in **Planner → Live →
Memory Reconciler → Quality Critic** flow. It shows configured storage mode,
recipient language and bounded workflow progress, resets pending consent between
recipients, and asks for fictional Google-processing acknowledgement before a
workflow call. Critic findings are private developer data, not portal recaps.

Use the backend's `docs/END_TO_END_TESTING.md` as the full runbook. Three modes
are supported: local SQLite, loopback Firestore emulator, or an explicitly enabled
isolated test Firestore database. Live test storage requires matching Firebase
anonymous auth and a backend operator UID allowlist; inspect the portal's
developer identity details to bootstrap that allowlist. No sign-in screen is
added. Restart the frontend after changing `.env.local`; `.env.example` documents
the public API/WS endpoint and optional Firebase key.

This supersedes earlier SQLite-only test instructions below. It does not migrate
existing data or authorize a product dashboard, real-family imports, shared
recaps or cloud deployment. Browser previews/identity and the private backend
voice-key vault remain local even when synthetic family state uses Firestore.

## Same-browser family simulator (schema v2)

Enable `LOCAL_DEMO_ENABLED=TRUE` on the local backend with development auth and
preset Live mode; leave frontend Firebase unset for SQLite/emulator testing.
Set `HUGBACK_WORKFLOW_ENABLED=TRUE` on the backend for additional specialists.

1. In **Family setup**, create a fictional family with its first recipient. Use
   **Add recipient** for Mother/Father/others (up to eight). Simulate each person's
   setup consent separately and choose their own wellbeing-memory permission.
2. Select a recipient explicitly. Their **Background**, saved previews, reviewed
   excerpts, call metadata, memory and voice selection are independent. Loading
   the page never chooses a recipient automatically.
3. Use **Try a synthetic example** or a fictional export; map the two speakers,
   then click **Prepare [recipient]'s background** after the separate fictional
   declarations. No message-by-message selection is needed. The browser
   considers every parent-authored text message and sends at most 24 dated
   excerpts. When suitable child replies exist, up to four are attributed style
   examples beside up to 20 parent excerpts; otherwise all 24 may be parent
   excerpts. Each excerpt is at most 500 characters. This
   bounded context is not the complete chat or an AI summary. **Save local
   preview** alone does not activate background in calls. Switching
   recipients resets the pending preview/review so it cannot carry over by mistake.
4. Optionally **Enable child voice** in Voice setup, then select each recipient
   and **Assign child voice**. A shared voice never shares memory. Standard voice
   is explicit per recipient; stale custom assignments block calls rather than
   silently acquiring a replacement voice or switching to standard.
5. **Test a call as [recipient]** opens `/?demo=parent&recipient=<id>`. A fresh family
   lookup precedes audio setup; the server rechecks membership, revision and exact
   voice assignment. Confirm fictional role-play/Google processing before audio.
   Changing the selected recipient resets role-play confirmation and subtitles.
   End a call before switching people; this does not recognize who is speaking.

The call test shows that recipient's processing status, not recaps; a new call
waits until their previous call/memory update finishes. Canonical wellbeing
concerns, cooldowns, recovery and privacy actions remain recipient-specific.

Storage: browser identity in localStorage; parsed previews in IndexedDB scoped
by owner + recipient; reviewed excerpts, call metadata and concerns in local
backend SQLite by default, or the explicitly selected test Firestore repository.
Five previews per recipient, forty total; seven-day local preview retention.
No cloud mode is enabled merely by loading the page. Keep the same browser/origin.

Old single-parent data is preserved as **Existing parent**, never guessed to be
Mother/Father or copied to them. Its old unassigned previews remain accessible
there. New recipients start with clean history and standard voice.

No recap-sharing change, real-family activation, automatic speaker recognition,
production phone linking or verified family membership is implemented here.

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
   In **Family setup**, enter the child’s gender once; it controls HugBack’s
   Hindi/Hinglish first-person wording when the child voice is assigned. The
   recording is not analyzed for gender. Existing voice profiles need no new
   recording for this setting. The backend sends both recordings to Google
   Voices with `store=False`, no
   creation model override, one transmission, bounded timeout and no automatic
   enrollment retry. `PERMISSION_DENIED` is not automatically diagnosed as a
   billing problem. Google acceptance is not proof of likeness/identity.
4. Enrollment returns metadata, never a provider key. Choose **Enable child
   voice**, select a recipient in **Family setup**, then use **Assign this voice
   to [recipient]** in Voice setup (or **Assign child voice** in Family setup).
   Voice setup shows its recipient-specific preview link only after assignment;
   if nobody is selected it sends you back to Family setup, not an unscoped call.
   Repeat for each intended recipient; enabling alone does not assign it. Both
   Mother and Father can use the same profile without sharing context or memory.
   Expiry, disablement, removal or replacement blocks stale assignments; reassign
   or choose **Use standard voice** for that recipient. Changes apply to **new**
   calls; end an active call first.
5. `/?demo=parent&recipient=<id>` resolves the voice from the browser operator
   before validating the selected recipient's membership, revision and voice.
   Only then does it resolve that recipient's memory scope. The WebSocket accepts an opaque
   `voiceProfileId`, never raw `voiceKey`. Gemini Live handles conversation and
   transcription; its preset audio is discarded, and only Google streaming TTS
   audio using that profile reaches playback. The key is NOT a Live voice ID.
   One ordered emitter with bounded one-phrase synthesis lookahead spans turns,
   cancels interrupted speech, closes SSE/client resources, and checkpoints
   emitted TTS off the audio path. Failures stop
   the call rather than mix preset/custom voices. Hugback remains disclosed AI.

   The backend now releases a shorter first phrase and can synthesize one queued
   phrase ahead; browser render cues still control subtitle visibility.
   `HUGBACK_TTS_LOOKAHEAD=0` on the backend disables overlap (which can spend
   synthesis on interrupted audio). No re-enrollment or frontend setting is
   required. This removes application waits, not the additional Google synthesis
   stage; real latency and voice quality still need authorized listening tests.

**Storage:** source audio is transient browser/backend memory, not saved by this
flow. A client-managed key and metadata persist in private mode-0600 SQLite at
`HUGBACK_VOICE_DB_PATH` (default backend `.local-voice/voices.sqlite3`), scoped to the
browser development identity. This vault is separate from synthetic family data,
gitignored and excluded from Docker context. It is not encrypted at rest. Raw audio
is sent to Google on explicit upload; `store=False` is not a blanket promise about
all provider processing/retention. The local expiry is the earlier of Google's
reported expiry and seven days; absent provider expiry, seven days is only a local
limit. Expired keys are purged on database access, not a background retention job.
Expired selected metadata remains to prevent silent preset fallback.

**Remove voice** removes the local key/selection, not Google's key or provider
retention, and does not terminate an existing call. Older browser IndexedDB
recordings are not migrated/uploaded automatically; a separate control deletes
them. Use the same browser profile, origin and backend; clearing browser identity
loses access. The local vault is single-machine/single-worker only. Firebase/cloud
voice storage, recovery, production enrollment, key revocation, provider likeness,
paid entitlement and real latency/quality validation remain explicit gates.

Offline checks: `python -m unittest discover -s tests -q` (backend virtualenv),
`npm test`, `npm run typecheck`, isolated frontend production build. Fixtures are
synthetic and all provider I/O is mocked. Never use real family material in tests.

### Replicated voice subtitle timing

Gemini Live can draft a response before Google TTS finishes synthesizing the
selected voice. The backend therefore suppresses the early replicated-voice
draft and attaches each spoken phrase's text to its first PCM chunk with
`outputTranscription.playbackAligned=true`. The browser queues the cue with that
audio and reveals it only when the worklet renders that chunk. Later phrases
wait for their own place in the playback queue; user transcription stays immediate.
Standard Live voice transcription is unchanged.

The speaking indicator follows render start/drain, not a three-second timer or
server `turnComplete`. Interruptions/end/error/recipient changes discard pending
cues. Empty buffers render silence; overflow fails rather than dropping audio
and misaligning subtitles. Refresh the frontend and restart/reload the backend
before testing this paired protocol update in a new call.

This is **phrase-level**, not word-level alignment. A phrase may still be cut
short by interruption. Rendering does not prove physical output or hearing:
[AudioWorklet processes rendering blocks](https://developer.mozilla.org/en-US/docs/Web/API/AudioWorkletProcessor/process),
and the browser/device adds output latency. No delivery acknowledgement is sent
to memory logic. This fixes early text display, not Google TTS synthesis latency,
and does not add paid requests, hosted services or transcript persistence.

## Identity: no sign-in screen

The same `src/lib/identity.ts` helper serves calls and portal HTTP requests.
With the existing `NEXT_PUBLIC_FIREBASE_API_KEY`, anonymous Firebase enrollment
and refresh happen automatically. Backend `HUGBACK_AUTH_MODE=firebase` must match
that project and verify ID tokens. Firebase anonymous auth must already be
enabled by an authorized operator; this patch does not enable it.

Without a configured Firebase key, only localhost/127.0.0.1/IPv6 loopback may
reuse the development UUID. The local backend was verified in `development`
mode during this change. A development ID never unlocks private cloud summaries.
Refresh errors do not erase credentials or silently create a replacement UID.
Same-origin Web Locks serialize enrollment/refresh where supported.

Browser data is not account recovery: clearing it, switching device or changing
origin (including localhost versus 127.0.0.1) can lose access. No recovery/linking
flow exists yet. Do not put real family data in local demos.

## What works now

- Three responsive sections and automatic identity with no login form.
- Local UTF-8 WhatsApp Android/iOS text preview with explicit date order,
  speaker mapping and timezone.
- Instagram **constrained** normalized text and one-conversation JSON preview,
  not all possible exports. Text format:

  ```text
  [2026-10-01T18:00:00+05:30] Parent: Hello
  [2026-10-01T18:01:00+05:30] Child: Hi
  ```

  Supported JSON has `participants: [{name: "..."}]` and
  `messages: [{sender_name, timestamp_ms, content}]`. Media-only entries are
  omitted. ZIP/HTML/whole-account exports and group conversations are rejected.
- Participant/date validation, message preview and IndexedDB save/delete.
  Limits: 1 MB / 2,000 messages / five imports. Seven-day expiry is checked and
  content removed on next access, not while the browser is closed.
- A synthetic example is provided, clearly labeled. Parsed text is rendered
  as text, never HTML or instructions.
- Voice setup now uploads adult own-voice + spoken consent to Google only on
  explicit submit, then offers separate custom/preset selection and removal.
  Existing browser recordings are never automatically uploaded or activated.
- The local synthetic family setup has a separate opt-in for bounded
  conversation signals. Medium/high-confidence, non-diagnostic call estimates
  appear in the selected recipient's portal card for up to 72 hours. They are
  labeled AI-estimated; low-confidence/unclear results display nothing. This
  signal feature does not store raw audio, transcript or model reasoning.
- The local synthetic Signals back section lists call dates and statuses, then
  fetches a short summary only when the selected recipient's separately
  consented test call is opened. The old approved-summary mailbox remains a
  separate backend prototype and is no longer shown in the simulator view.

## Not activated or implemented

Outside the explicit synthetic demo review flow, background previews are
**not uploaded, AI-extracted or used in calls**. Real
intake needs dual consent, trusted parent linkage, provenance, minimization,
extraction, durable processing and deletion. The summary API reader requires a
trusted exact-content parent-approval producer; that producer and enrollment
are not wired. Real-family email notifications, recovery, phone voice enrollment and verified
custom-voice likeness are not implemented. No cloud resources were provisioned.

## Local checks

```sh
npm test
npm run typecheck
npm run dev
```

Use an isolated copy for `npm run build` while the existing development server
is running; do not overwrite its `.next` output. No new test dependency is used.
Browser-test with the built-in fictional example, not family history.
