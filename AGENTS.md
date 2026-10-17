# Hugback frontend

- 18 October: user approved the hosted synthetic demo without manual UID
  approval/invitations. Keep Firebase anonymous authentication and recipient
  isolation. Public demo admission is a separate explicit backend setting,
  not authority from a browser flag. Hosted build uses the synthetic recipient
  flow, both standard and consented adult child voice, and fictional-data notice.
  Firestore mode stores the child key/profile in a backend-only collection in
  the same named DB; never send keys to browsers or upload audio implicitly.
  This supersedes the local-only voice-vault rule below; production family
  intake remains separately gated. Do not promise real-family
  consent or durable post-call processing.

- 13 October: fictional browser imports use one action after whole-chat simulated
  child and parent permission, rather than individual message checkboxes. The
  browser considers all parent-authored text messages and sends at most 24
  dated excerpts to the selected demo recipient. When suitable child replies
  exist, include up to four short, attributed style examples alongside up to
  20 parent excerpts; otherwise all 24 may be parent excerpts. Clearly state
  that long chats are bounded and not fully recalled; never present this as
  real-family consent, full-file upload or production intake.

- 13 October: Signals back now shows only a brief AI-generated call summary for
  future fictional calls, scoped by recipient/date. Never render raw call turns
  or fetch the former transcript endpoint. An absent summary is unavailable,
  not an invitation to show raw text. Summary sharing keeps the existing demo
  consent gate; revocation removes saved summaries and any legacy test turns.

- 13 October: Signals back may show synthetic topic notice status beside the
  separately consented call transcript. Demo setup may simulate one standing
  parent permission for brief post-call email notices; browser fields never
  choose the actual email destination. Show unconfigured, failed and sent states
  accurately, without implying emergency monitoring or diagnosis.

- Earlier full-transcription display guidance below is superseded by the
  summary-only rule above. No per-call
  approval. Real call history requires verified parent enrollment and standing
  transcript-sharing consent, not the browser role selector. The demo view must
  never imply real call history is connected. This supersedes the older blanket
  no-transcript and recap-exclusion bullets below for this narrow simulator flow.

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
- The child supplies gender in Family setup once for the synthetic family;
  existing families can update it there with a revisioned owner-scoped request.
  This controls Hindi/Hinglish first-person form for the assigned child voice.
  The standard voice uses feminine wording. Voice setup never classifies the
  recording or asks for a gender choice, and old voice profiles remain usable.
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
