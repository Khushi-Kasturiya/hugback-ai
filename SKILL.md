---
name: gemini-native-audio-integration
description: Instructions for implementing low-latency, bidirectional audio streaming using the Gemini Live API via WebSockets.
---

# INSTRUCTIONS

When tasked with building or modifying the real-time voice integration for Hugback, you MUST adhere strictly to the following Google Cloud Platform specifications. DO NOT use third-party APIs like OpenAI, ElevenLabs, or Twilio for core AI generation.

## 1. WebSocket Connection Setup
- Use the Google Cloud AI Platform WebSocket endpoint for bidirectional streaming.
- Route connection: `wss://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/publishers/google/models/{MODEL_ID}:streamGenerateContent`
- **Target Model:** `gemini-live-2.5-flash-native-audio` (or latest Gemini native multimodal equivalent).
- Authenticate using Application Default Credentials (ADC) via the Google Auth Library to fetch the Bearer token.

## 2. Initializing the Session
- Upon opening the WebSocket, immediately send a `setup` message containing the `system_instruction` and configuration parameters.
- **System Prompt Requirements:** Instruct the model to use natural human disfluencies ("hmm", "accha", brief pauses) and maintain short, conversational bursts.
- Inject the parent's current state retrieved from Vertex AI MemoryBank directly into the `setup` context.

## 3. Audio Ingestion & Formatting
- The client streams audio to the Cloud Run broker.
- **Strict Format:** Audio MUST be processed and sent to the Gemini API as `16-bit PCM` at `16kHz`.
- Encode the raw PCM chunks in `base64` before wrapping them in the `realtime_input` JSON payload.

## 4. Handling Barge-In & Interruptions
- You must implement a Voice Activity Detection (VAD) interrupt sequence.
- When the user interrupts, the client sends an interrupt flag. 
- The broker MUST immediately stop playing the current TTS output buffer.
- The broker MUST send a `client_content` payload to the Gemini API with the flag `"turn_complete": true` to signal that the user has taken back the floor.

## 5. Output Handling (Chirp 3 Integration)
- The text output stream from Gemini must be captured in sentence-level chunks.
- Pass chunks immediately to Google Cloud TTS (Chirp 3) to generate the custom voice clone.
- Stream the returning audio (`24kHz PCM`) back to the client via WebSockets to minimize time-to-first-byte (TTFB) latency.