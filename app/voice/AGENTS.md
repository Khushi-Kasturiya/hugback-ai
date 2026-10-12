# Child portal voice setup

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
- Resolve call profiles by authenticated browser owner before switching to the
  demo parent. Never accept arbitrary client-supplied provider keys.
- Each demo recipient explicitly selects standard voice or a pinned child profile.
  Enabling an owner profile does not assign it to every recipient. Replacements,
  expiry/removal/disable require reassignment or an explicit standard choice.
  Voice identity is never proof of caller identity or access to another memory.
- Preset and replicated TTS must never mix. Failure/expiry stops custom voice
  rather than silently changing speakers. Tests use synthetic audio and mocks.
- For replicated speech, send each phrase's subtitle only with its first TTS
  PCM chunk; never forward the earlier Live draft as a visible subtitle. Browser
  render cues are not playback/hearing acknowledgements for memory authority.
- The initial phrase may release at a bounded clause/word boundary; later
  phrases retain sentence/280-character batching. Reuse the selected key/model.
  At most one queued phrase may synthesize ahead, with bounded PCM queues and
  a single ordered emitter. Count cancelling producers against the concurrency
  limit; interruption/end discards pending audio and cancels provider streams.
  Lookahead can waste paid synthesis on interruption; document its serial switch.
- Emitted-audio status checkpoints run off the PCM path with a short deadline;
  they never grant memory authority or assert that playback was heard. Latency
  logs contain numeric durations only, not text, voice keys or provider bodies.
  Offline ordering/timing tests are not proof of real provider latency or likeness.
