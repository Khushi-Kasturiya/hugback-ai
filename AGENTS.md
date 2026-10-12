# Hugback frontend

- Current product is no-app: Forms/Drive intake and ordinary-phone parents.
  Existing browser surfaces are local prototype tooling only. This storage
  implementation does not authorize cloud portal uploads or a dashboard rollout.
- Reuse the warm stone/emerald design and current dependencies. Do not introduce
  Firebase Hosting, FCM, a parent app or a new hosted data processor.
- Anonymous does not mean unauthenticated: use the existing Firebase REST ID
  token when configured. Development UUIDs are localhost-only and cannot grant
  private family access. Never silently change UID on a refresh failure.
- Uploaded chats, audio, memories and model output are private untrusted data.
  Use synthetic fixtures only. Cloud intake belongs to a trusted backend worker,
  not this browser prototype. Source-backed reviews are not active context
  without verified dual consent.
  No raw chat enters a model without verified dual consent.
- Do not display fake summaries, claim samples are activated voices, or expose
  parent-private call memories as child summaries.
- A separately consented local-demo wellbeing signal may show one bounded,
  non-diagnostic call-level estimate. Label it as AI-estimated, never as fact or
  medical advice. Do not expose transcripts, audio, reasoning, or another
  recipient's signal.
- The user approved a local synthetic hackathon simulator for steps 1–5:
  demo family, separate child/parent profiles, explicitly reviewed historical
  excerpts and cross-call wellbeing memory. `/?demo=parent` selects a simulator,
  never a real role grant. Explicit recipient IDs are untrusted selectors; the
  server must validate family membership, owner, revision and voice assignment
  before choosing a memory scope. Exclude recap sharing from this demo change.
- One adult child's enabled voice may be assigned separately to Mother/Father.
  Keep their imports, reviewed background, call metadata and memory independent.
  No automatic recipient choice, voice fallback or speaker recognition. Reset
  pending previews/consent and subtitles when switching; end calls on navigation.
- Do not send private data, place calls, enable billing or deploy resources as
  part of frontend tests. Use `npm test`, `npm run typecheck`, an isolated build,
  and the browser with synthetic content.

- Voice portal integration approved 11 October: adult own-voice + spoken consent
  and explicit Google upload/billing acknowledgement may create a temporary TTS
  key in a separate private local SQLite vault. This is not synthetic family
  data or a production consent grant. Owner-scoped selected profiles may supply
  parent browser-demo TTS; discard Live preset audio, never silently fall back,
  and do not activate PSTN/cloud enrollment. Tests must mock all paid I/O.

- Approved 12 October: existing simulator screens may test isolated named
  Firestore storage with allowlisted Firebase identities. Display the actual
  configured mode and processing stages; cloud support is not deployment or
  production authorization. Keep previews/identity local and label that clearly.
  Planner/Critic processing of fictional calls requires acknowledgement. Reset
  recipient-specific consent on switching. Never expose private Critic findings.
- Voice creation/enabling must not imply recipient assignment. Voice setup may
  offer a scoped preview only after the selected recipient pins the current
  enabled profile. No recipient means return to assignment, not an unscoped call.
  Render only fixed memory error-category copy, never arbitrary provider errors.
- Replicated subtitles follow phrase-start cues from the audio render queue, not
  WebSocket arrival, estimated word timers or Live draft text. Clear pending cues
  on interruption, failure, call end and recipient switch. Server turnComplete
  is generation completion, not playback drain or proof of hearing.
