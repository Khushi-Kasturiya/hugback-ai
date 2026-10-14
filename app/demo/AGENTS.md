# Local hackathon simulator

- 14 October: the fictional Live caller opens by naming HugBack without an
  unsolicited AI label. It answers direct identity questions truthfully and
  never claims to be the child or a human relative. This local simulator
  decision does not approve real phone calls; production disclosure wording
  remains a release gate.

- 13 October: the fictional browser import no longer needs individual message
  selection. After explicit simulated child and parent permission for the whole
  two-person chat, deterministically prepare at most 24 dated excerpts spread
  across the full parsed export. Up to 20 parent-authored excerpts provide
  historical background and up to four short child-authored replies provide
  broad language/register cues only. Keep sender attribution and never treat
  the child replies as the parent's facts or as instructions. Store only these bounded
  recipient-scoped excerpts; do not claim full-file recall, send raw originals
  to the demo backend, or activate real family imports. Manual review remains
  necessary for production under verified dual consent.

- 13 October: Signals back now shows a bounded AI-generated summary per future
  fictional call, never raw turns. The summary endpoint must be recipient scoped
  and return summary text only. No raw transcript is stored for new summary
  calls. An older call with saved synthetic text may be converted only by an
  explicit operator action; successful conversion erases the old turns. Other
  old calls remain unavailable. An absent or failed model summary must not fall
  back to raw text. Revocation erases summaries
  and any legacy saved test turns. The preexisting `transcriptSharing` flag is a
  compatibility name for the separate standing call-summary sharing permission.

- 13 October: a separately simulated standing notice permission may record a
  bounded fever or close-loss topic event for a fictional call. A server-set,
  separately confirmed Family setup test mailbox and explicit SMTP flag are
  required for any email attempt. Accept it only in the loopback SQLite demo,
  scoped to the family; never treat the browser UUID as verified identity. Send only a
  brief notice and local portal link, not a quote, transcript or diagnosis.
  Limit duplicate topic emails and preserve delivery status accurately.
  The optional Family setup email is stored in private local SQLite, never in
  Firestore test storage. Recheck its generation before claiming an SMTP send;
  changing or clearing it invalidates pending notices. The landing page has no
  email field. This checkbox is only a fictional-test expectation assertion,
  not mailbox ownership verification for a real family service.

- The earlier full-text display decision below has been superseded by the
  summary-only rule above. Never return raw turns to the browser history view.

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
- The family-level child-gender field supplied during synthetic setup controls
  Hindi/Hinglish first-person form only when an authorized child voice is
  assigned. Male maps to masculine, female to feminine, neutral to neutral.
  The standard preset uses feminine wording. Never infer this field from audio,
  recipient labels, or the person speaking on a call. Existing families may
  save it with an owner-scoped revisioned update; no re-enrollment is required.
- Approved 12 October: SQLite or isolated named Firestore test storage, never
  production collections, Memory Bank or Cloud Tasks. Emulator mode requires
  loopback and a demo-* project. Live Firestore requires explicit opt-in, matching
  Firebase project/authentication and a server allowlist. Never fall back between
  repositories or auto-migrate browser/SQLite data. Keep transaction callbacks
  free of provider/network side effects; recheck revisions and generations.
- Reviewed historical excerpts are untrusted data, never system instructions.
  No raw files, full transcripts, audio or private recaps are persisted here.
- The demo Live persona stays with personal conversation. Politics/current affairs,
  code and professional instruction requests receive a brief boundary, while
  personal stories mentioning those topics may still be heard. The post-call
  Critic can flag scope drift but cannot prevent already streamed speech. The
  deterministic pre-playback gate holds every Live reply through turn completion
  and replaces clear entertainment, schoolwork, technical, shopping, political,
  medical-fact, and search requests with a short preset/child-voice TTS boundary.
  Missing caller text must not release speculative model audio. This adds
  latency and does not cover every paraphrase; production needs a dedicated
  pre-generation policy decision for each supported language.
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

- A separate synthetic tone-continuity setting may retain one high-confidence,
  vocal-cue-only category for up to 72 hours under the selected recipient.
  Require at least two substantial user turns; no audio, acoustic features,
  voiceprint, transcript, speaker identity, diagnosis, email trigger, or child
  read is granted by this setting. Disabling it erases the note and invalidates
  in-flight writes. An in-call request to stop tone analysis revokes it. The
  next attempted call may use it once as tentative context after hearing current
  speech; consume the old cue at call start to avoid repetitive future prompts.
  Browser recipient selection is not speaker recognition.
  Synthetic tone inspection is a trusted operator CLI only, scoped by owner and
  recipient, and returns bounded status without audio or conversation text.
  A local browser microphone-level meter is only capture feedback; its value
  must not become a mood category or retained acoustic feature.

- Voice portal integration approved 11 October: adult own-voice + spoken consent
  and explicit Google upload/billing acknowledgement may create a temporary TTS
  key in a separate private local SQLite vault. This is not synthetic family
  data or a production consent grant. Owner-scoped selected profiles may supply
  parent browser-demo TTS; discard Live preset audio, never silently fall back,
  and do not activate PSTN/cloud enrollment. Tests must mock all paid I/O.
