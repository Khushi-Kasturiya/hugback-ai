# Architecture

[Project overview](../README.md) · [Development](DEVELOPMENT.md) ·
[Data and safety](DATA_AND_SAFETY.md)

## Two scopes, deliberately separate

**Implemented hackathon path:** a synthetic browser simulator with a Next.js
interface and FastAPI audio/policy broker. Hosted mode uses Firebase anonymous
identity and one explicitly selected named Firestore database. SQLite and a
loopback Firestore emulator are testing adapters, not alternative production
databases or silent fallbacks.

**Intended phone service:** an adult child supplies setup through Google
Forms/Drive; a parent uses an ordinary phone. Trusted enrollment, consent
verification, automatic submission routing and a carrier adapter are not
completed by the simulator. No parent app or production child dashboard is
required by that design.

## Request and audio path

1. The browser obtains a Firebase ID token in hosted mode. HTTP requests and
   the WebSocket handshake use the same identity. Loopback-only development IDs
   cannot unlock hosted data.
2. The broker validates the exact Origin, token-derived owner, explicit
   recipient membership, revision, call lease and selected voice profile before
   connecting to Google. Client IDs are selectors, not authority.
3. Microphone PCM is sent through `/ws` to Gemini Live. Standard speech uses
   the configured preset. For a pinned custom voice, the broker discards Live
   preset audio and synthesizes released text through Google streaming TTS.
4. A bounded companion-scope gate can replace clear external-information
   requests before playback. This is pattern-based, adds latency and does not
   guarantee detection of every paraphrase.
5. The ordered audio queue handles interruption and cancellation. Custom-voice
   subtitles follow phrase-start playback cues, not arrival of Live draft text.
   Generated, emitted and actually heard are different events; there is no
   claim that a playback cue proves the listener heard a sentence.

Custom-voice failures stop that path rather than mixing voices. Standard voice
requires no custom key. Provider likeness, timbre consistency and real latency
require separate listening tests.

## Four stages and their authority

| Stage | Responsibility | Limit |
| --- | --- | --- |
| Planner | Select a bounded, source-linked conversational plan before the call. | Cannot select a different owner, recipient or consent grant. |
| Live | Conduct the conversation and make bounded tool proposals. | Only speaking agent; not a general-purpose task or medical assistant. |
| Memory Reconciler | Propose evidence-linked observations after the call. | Does not write directly; exact source, scope, schema and consent are rechecked. |
| Quality Critic | Evaluate assistant behavior after reconciliation/commit. | Developer-only codes, not a diagnosis, child recap or a source of memory authority. |

The deterministic write boundary validates:

```text
authenticated owner → recipient membership → revision / lease
→ current consent generation → bounded schema → exact source evidence
→ transactional commit
```

Model output, imported chats and transcripts remain untrusted data. Critic
failure does not erase an otherwise valid memory commit. Optional call
summaries use a separate bounded summarizer and separate sharing permission;
they are not the Critic report.

## State and storage

| Data | Hosted synthetic mode | Local mode |
| --- | --- | --- |
| Family, child and recipient settings | Named Firestore | Private SQLite test repository |
| Consents, bounded background, call metadata and memory | Recipient-scoped Firestore records | Same contracts in SQLite |
| Optional summaries, notice status and private Critic codes | Same recipient-scoped repository | Same repository |
| Temporary voice keys and profile/enrollment metadata | Separate backend-only collection in the same named DB | Separate private SQLite vault |
| Identity tokens or development ID | Browser localStorage | Browser localStorage |
| Full parsed chat previews and prototype photo | Browser IndexedDB | Browser IndexedDB |
| Source voice recordings | Transient memory and explicitly authorized Google processing; not persisted by the app | Same |
| Authorized original chat export | Separate internal private GCS intake, disabled in synthetic Firestore mode | Offline validation fixture only |

The fixed hosted collections are `hugback_synthetic_test_families`,
`hugback_synthetic_test_recipients` and `hugback_private_voice_profiles`.
Family metadata is separate from recipient state, so one parent's call does not
rewrite another parent's history. A shared adult voice grants no shared memory.
All browser Firestore access must be denied; server SDK access is controlled by
backend IAM, not Firebase client rules.

Browser preview is intentional data minimization. Selecting a file does not
upload it. Preparing background sends at most 24 attributed excerpts, including
up to four short child style examples when available. Structured context
extraction is separately configurable; the full import is not call context.

## Hosted admission

Remote access and public admission are separate backend gates. Public mode
allows a new visitor with a valid Firebase token from the configured project
without a manual UID list. Restricted mode still requires that list. Neither
mode waives exact HTTPS Origin, membership, lease, revision or consent checks.

The public URL is not a secret, judge restriction or quota. Anonymous identity
isolates demo owners; it does not verify real family relationships or establish
production consent. Losing browser identity has no implemented recovery flow.

## Durability and diagnostics

Firestore persists **committed state**, not unfinished model work. The synthetic
Reconciler/Critic path is process-local. Summary persistence and its optional
email attempt are awaited in a shielded WebSocket finalizer, but a container
crash can still lose work. There is no durable demo outbox or email retry queue.

The repository also contains older Memory Bank and Cloud Tasks modules.
`MEMORY_PROCESSING_MODE=cloud_tasks` applies to that legacy path, not the
synthetic four-stage workflow. Keep production/legacy flags off in named
synthetic Firestore mode.

The frontend `/architecture` view reads `GET /api/architecture`; `/health`
also reports selected settings. These are content-free configuration manifests,
**not** successful Firestore, model, IAM or delivery probes. A canonical-service
label is not evidence that its production integration is active.

## Code map

- [Broker and lifecycle](../backend/app/main.py)
- [Authentication and configuration gates](../backend/app/auth.py),
  [settings](../backend/app/config.py)
- [Synthetic policy and repositories](../backend/app/demo/)
- [Planner, Reconciler and Critic](../backend/app/workflows/)
- [Voice enrollment, vault and playback](../backend/app/voice/)
- [Browser audio integration](../frontend/src/hooks/useLiveAudio.ts),
  [audio queue](../frontend/src/lib/audio-player.ts)
- [Separate internal original-intake module](../backend/app/family/)
