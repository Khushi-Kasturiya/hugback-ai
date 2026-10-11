# Elara - Technical Specifications

> **Retained-original storage (11 October 2026, v4.5):** Internal Forms/Drive
> intake sink with private exact-byte Cloud Storage originals, Firestore
> recipient metadata, source-index review and repeat-safe partial-write recovery.
> No expiry or auto-delete after processing. Offline-by-default operator command;
> no new browser API, resource provisioning or local-demo migration.
> See `docs/CLOUD_INTAKE.md`. Automatic Forms/Drive pickup, verified identity and
> consent, extraction, activation, deletion and phone integration remain gated.
> Current no-app direction supersedes the historical portal exceptions below.

> **Current family model (11 October 2026, v4.4):** One adult-child voice owner,
> separate Mother/Father/other recipients, each with isolated background, calls,
> wellbeing memory, consent, revision and voice choice. Implemented locally in
> SQLite schema v2. Calls require an owner-validated recipient and current revision;
> a shared enabled voice must be assigned individually and never shares memory.
> Legacy history stays under Existing parent, not copied to new recipients.
> Product remains no-app with Forms/Drive intake; existing browser code is an
> internal synthetic simulator. Phone identity/linking, production multi-recipient
> authorization and cloud enrollment remain gates. No speaker recognition or
> recap-sharing change is included. This supersedes older single-parent wording.

> **Latest voice exception (11 October 2026):** The child portal now connects the
> operator-reported paid Voices + TTS flow to local test calls. Explicit adult
> own-voice/upload consent, owner-scoped local SQLite keys, separate activation,
> expiry, no preset fallback and mocked tests apply. See README. Telephone and
> production enrollment remain gated; earlier research notes below are historical.

> **Local hackathon simulator (11 October 2026):** The user approved steps 1–5:
> fictional chat setup/review, separate server-issued demo child/parent IDs,
> same-browser parent-call switch, reviewed historical context and canonical
> cross-call wellbeing memory. This is isolated SQLite, not production
> Firestore or verified enrollment. Recap sharing is excluded from this change.
> Feature flag + development identity + loopback peer/local Origin are required.
> See README and `app/demo/AGENTS.md`. No live call or cloud resource is authorized
> merely by implementing the simulator.

> **Child portal exception (11 October 2026):** The user now explicitly permits a
> narrow child-facing `/childportal` in the existing frontend, with automatic
> anonymous identity and no sign-in form. Parents remain phone-only. Local
> import preview, voice preparation and gated shared-summary reads are implemented;
> real-family background activation, parent linking/approval production, email and recovery
> are not. This supersedes older blanket "no dashboard" statements only for this
> scope. No production deployment, monitoring, impersonation or cloud provisioning
> is authorized. See README and `app/portal/AGENTS.md`.

> **Canonical follow-up pilot (11 October 2026):** The backend now includes an
> opt-in Firestore lifecycle for direct-call wellbeing reports, source/time
> validation, one follow-up reservation per call, cooldowns, explicit
> resolution/suppression, and deletion-generation fences. Defaults remain OFF.
> Local synthetic tests are not a deployed-memory claim. Trusted parent consent,
> real provider/Firestore tests, a durable processing outbox, and dormant-record
> purge scheduling remain gates. No raw transcript persistence is enabled by
> this pilot. See README and `app/memory/AGENTS.md` before extending it.

> **Voice consistency hardening (11 October 2026):** Ordinary calls now use
> `ELARA_LIVE_VOICE_MODE=preset` and reject browser enrollment overrides before
> Google. The explicit `experimental-inline` operator mode requires both
> recordings and a provider consent acknowledgement before readiness, with no
> preset fallback and no likeness claim. The prompt asks for one disclosed AI
> speaker. This is local routing/prompt hardening, not fine-tuning or a verified
> acoustic fix. See README for the synthetic listening-test gates. No frontend
> product, carrier integration, cloud deployment, or live experiment is enabled.

> **Current-direction note (10 October 2026):** The roadmap below predates the
> no-app architecture in
> `/Users/pratham.gupta/Documents/ChatGPT/ELARA/docs/Elara_No_App_Architecture_v4.md`.
> That architecture remains authoritative; this historical text does not
> authorize a dashboard, monitoring service, or impersonation.
>
> **Local voice experiment:** `scripts/check_live_voice_replication.py` now
> supports private file paths, offline validation, explicit in-memory reference
> selection, and distinct Cloud PCM / SDK WAV probes. It is offline by default.
> Real use requires explicit consent and live-request flags, plus provider-access
> and data-handling checks. A generated WAV filename is not entitlement evidence.
> Configured recordings are not automatically used in ordinary calls. See the
> README for the exact flags and limitations; native voice remains unverified.
>
> **Voice test outcome (11 October 2026):** The SDK-WAV Live probe returned audio
> but failed the operator's speaker-likeness check. This is not successful cloning.
> The isolated probe now requires explicit server consent-verification evidence
> before requesting speech; that evidence alone still cannot prove voice likeness.
> No new voice is enabled for ordinary calls.
>
> **Separate TTS probe:** `scripts/check_tts_voice_replication.py` is offline by
> default. Authorized use creates a client-managed voice key and passes it to TTS
> synthesis, not Live. It uses the configured API key's project independently of
> the browser account. Access, billing and likeness are still real-test gates.

**Hackathon:** Google Cloud AI Builder Cup 2026
**Theme:** Sustainability & Social Impact
**Lead Architect:** Khushi Kasturiya
**Constraint:** 100% Google Cloud & Google AI Stack (Strict)

## 1. Product Vision
Elara is a proactive, agentic audio companion designed to bridge the gap between elderly parents in their hometowns and their adult children overseas. It uses real-time, low-latency native audio, episodic memory, and voice cloning to simulate an empathetic, human-like phone call with the parent, actively monitoring for health and mood anomalies.

## 2. Core Architecture
- **Frontend / Client:** Next.js web application functioning as an audio client optimized for seniors (zero complex UI).
- **Backend Orchestration:** Python WebSocket broker (built locally first, deployed to Google Cloud Run).
- **LLM & Reasoning:** Gemini Multimodal Live API (Native Audio streaming via WebSockets) for real-time conversation and affective tone analysis.
- **Voice Synthesis:** Google Cloud TTS (Chirp 3: HD) customized with the child's voice profile.
- **State & Memory:** Vertex AI Agent Engine Memory Bank for long-term episodic memory (tracking health/mood over time without context window bloat).
- **Scheduling:** Google Cloud Scheduler and Cloud Tasks for proactive outbound call triggers.

## 3. Phased Execution Roadmap
*Agents must execute these phases sequentially. Do not attempt to build Phase 3 before Phase 1 is fully tested and functional.*

### Phase 1: The Core Brain & Bidirectional Audio (MVP - Local Development)
**Goal:** Establish a low-latency, vanilla voice conversation locally without custom cloning or memory.
- Set up a basic Next.js web client to capture microphone input and play audio.
- Build a local Python WebSocket broker (e.g., using FastAPI or the `websockets` library running on `localhost`) to handle bidirectional streaming to the `gemini-live-2.5-flash-native-audio` model.
- Authenticate locally using a Vertex AI Service Account JSON key (`GOOGLE_APPLICATION_CREDENTIALS`).
- Implement edge Voice Activity Detection (VAD) on the Next.js client to handle interruptions/barge-in (sending `turn_complete: true`).
- *Definition of Done:* The user can talk to the default Gemini voice in real-time via `localhost`, and interrupt it seamlessly without crashes.

### Phase 2: The Long-Term Memory (Vertex AI Memory Bank)
**Goal:** Give the agent episodic memory so it remembers yesterday's conversations.
- Integrate Vertex AI Agent Engine Memory Bank via the Python backend.
- Implement a post-call hook using the `GenerateMemories` function to extract salient health/mood facts about the parent.
- Configure the agent's initialization payload to preload these memories via similarity search before the next call starts.
- *Definition of Done:* The agent asks follow-up questions about a headache mentioned 24 hours ago.

### Phase 3: The Acoustic Identity (Chirp 3 Voice Cloning)
**Goal:** Replace the default AI voice with the child's custom voice.
- Intercept the text/audio stream from Gemini on the local Python broker.
- Route Gemini's output chunks to Google Cloud TTS (Chirp 3) to synthesize the cloned voice.
- Stream the 24kHz PCM Chirp audio back to the local Next.js client.
- *Definition of Done:* The agent responds in the child's exact voice with minimal Time-To-First-Byte (TTFB) latency.

### Phase 4: Cloud Deployment, Proactive Orchestration & Child Dashboard
**Goal:** Containerize the local broker, deploy to GCP, and automate the outbound calls/notifications.
- Containerize the Python WebSocket broker (using Docker) and deploy it to Google Cloud Run.
- Use Cloud Scheduler to trigger the Cloud Run webhook daily.
- Build the Firebase backend to log the daily health/mood digest.
- Push alerts via Firebase Cloud Messaging (FCM) to the child's dashboard if distress is detected.
- *Definition of Done:* The live system initiates a call automatically at 9:00 AM and sends a summary to the child at 9:15 AM.
