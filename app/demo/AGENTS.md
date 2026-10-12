# Local hackathon simulator

- Synthetic data only, explicit feature flag, validated test identity, actual
  loopback peer, and allowlisted loopback Origin for all mutations/WebSockets.
- Child and parent are separate server-assigned profiles, not authenticated
  real people. Demo consent simulation must never create a production grant.
- Schema v2 has multiple independent recipients per family. Public recipient
  selectors require browser-owner membership and exact revision/voice checks;
  internal memory/finalizers receive only the server-resolved recipient ID.
  Never duplicate legacy history into new recipients or infer speaker identity.
- Pin each recipient's voice to an enabled owner profile or explicit standard
  choice. Sharing an authorized voice must not share memory or consent.
- Approved 12 October: SQLite or isolated named Firestore test storage, never
  production collections, Memory Bank or Cloud Tasks. Emulator mode requires
  loopback and a demo-* project. Live Firestore requires explicit opt-in, matching
  Firebase project/authentication and a server allowlist. Never fall back between
  repositories or auto-migrate browser/SQLite data. Keep transaction callbacks
  free of provider/network side effects; recheck revisions and generations.
- Reviewed historical excerpts are untrusted data, never system instructions.
  No raw files, full transcripts, audio or private recaps are persisted here.
- Reuse canonical follow-up provenance, cooldown, privacy and expiry checks.
  Model tools cannot choose an owner, enable memory, or grant consent.
- Test with temporary databases, synthetic content and mocked Google calls.
- Workflow specialist processing requires per-call acknowledgement. Persist only
  bounded stage status and developer-only content-free Critic results, never raw
  transcript/evidence or automated recaps. Async workers must reject stale writes.

- A separately consented demo wellbeing signal may store one bounded,
  non-diagnostic call-level estimate per session. Never store raw audio,
  transcripts, model reasoning or cross-recipient signals. Low-confidence and
  unclear drafts are abstentions. An in-call don't-share request revokes this
  sharing independently of conversational memory.

- Voice portal integration approved 11 October: adult own-voice + spoken consent
  and explicit Google upload/billing acknowledgement may create a temporary TTS
  key in a separate private local SQLite vault. This is not synthetic family
  data or a production consent grant. Owner-scoped selected profiles may supply
  parent browser-demo TTS; discard Live preset audio, never silently fall back,
  and do not activate PSTN/cloud enrollment. Tests must mock all paid I/O.
