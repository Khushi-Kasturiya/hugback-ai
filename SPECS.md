# Elara - Technical Specifications
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