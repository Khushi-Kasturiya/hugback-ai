# Child portal voice setup

- 18 October updated approval: both standard and explicitly consented adult
  child-voice enrollment are approved for the hosted synthetic demo. Firestore
  mode stores temporary voice keys/profile metadata in the SAME named database,
  in a backend-only collection with deny-all browser rules and appropriate IAM.
  Verify rules before enabling HUGBACK_FIRESTORE_VOICE_RULES_CONFIRMED. No raw
  recordings, direct browser key reads, SQLite fallback or silent migration.
  Distributed transactional owner leases fence stale enrollment responses.
  This supersedes the earlier local-only vault rule below, not the consent,
  recipient isolation, no-fallback, real-phone enrollment or provider gates.

- The user approved connecting the pulled Google Voices + streaming TTS flow to
  the local child portal. This is not telephone enrollment or a production role grant.
- Adult own-voice confirmation, separate spoken consent and explicit Google
  upload/billing acknowledgement are required. Never imply verified likeness.
- Only authenticated loopback development callers, or explicitly allowlisted
  Firebase synthetic-test operators (approved 12 October), with an allowlisted
  loopback Origin can use the local voice vault. The vault stays local. Prefix
  Firebase ownership to prevent collision with development IDs; no automatic
  ownership migration. Production Firebase/cloud enrollment is a separate gate.
- Store only a temporary provider key and metadata in the private, gitignored
  SQLite vault. Never persist recordings, expose keys to the browser or log them.
- Do not classify gender or speaking form from the voice recording. The
  synthetic family stores the child-provided gender separately from the private
  voice vault. Existing voice profiles remain usable without re-enrollment.
- Resolve call profiles by authenticated browser owner before switching to the
  demo parent. Never accept arbitrary client-supplied provider keys.
- Each demo recipient explicitly selects standard voice or a pinned child profile.
  Enabling an owner profile does not assign it to every recipient. Replacements,
  expiry/removal/disable require reassignment or an explicit standard choice.
  Voice identity is never proof of caller identity or access to another memory.
- Preset and replicated TTS must never mix. Failure/expiry stops custom voice
  rather than silently changing speakers. Tests use synthetic audio and mocks.
- A standard Live call pins one configured preset for its session. Before
  forwarding preset PCM to the 24 kHz browser player, reject missing or
  mismatched sample-rate metadata and malformed PCM; never play it at an
  assumed rate that could change the apparent pitch. Keep the replicated
  voice key and TTS style fixed across phrases. Provider timbre consistency
  is not independently verified by these settings.
- The companion-scope gate holds each Live reply until the caller's current
  turn has finalized text. It replaces clear external-information requests
  with bounded TTS using the same selected preset name or child voice key,
  and discards held Live audio and transcript before playback. This adds
  one-turn latency and a different TTS engine may sound somewhat different.
  Pattern matching is not a universal semantic boundary; never claim perfect
  voice identity or guaranteed blocking of every paraphrase.
- For replicated speech, send each phrase's subtitle only with its first TTS
  PCM chunk; never forward the earlier Live draft as a visible subtitle. Browser
  render cues are not playback/hearing acknowledgements for memory authority.
- The initial phrase may release at a bounded clause/word boundary; later
  phrases retain sentence/280-character batching. Reuse the selected key/model.
  Keep a very short opening interjection with the following thought while text
  is still arriving; flush a complete short reply when the turn ends. Standard
  Live audio and replicated TTS use the same conversation instruction. Voice
  selection changes audio delivery, not the companion's identity or boundaries.
  At most one queued phrase may synthesize ahead, with bounded PCM queues and
  a single ordered emitter. Count cancelling producers against the concurrency
  limit; interruption/end discards pending audio and cancels provider streams.
  Lookahead can waste paid synthesis on interruption; document its serial switch.
- For both preset and replicated speech, emitted-audio status checkpoints run
  only after audio is sent, off the PCM path with a short deadline;
  they never grant memory authority or assert that playback was heard. Latency
  logs contain numeric durations only, not text, voice keys or provider bodies.
  Offline ordering/timing tests are not proof of real provider latency or likeness.
  First-phrase segmentation/lookahead applies only after the scope gate releases
  text, not permission to synthesize or play an unchecked Live draft.
