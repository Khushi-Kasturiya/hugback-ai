# Child portal voice setup

- The user approved connecting the pulled Google Voices + streaming TTS flow to
  the local child portal. This is not telephone enrollment or a production role grant.
- Adult own-voice confirmation, separate spoken consent and explicit Google
  upload/billing acknowledgement are required. Never imply verified likeness.
- Only authenticated loopback development callers with an allowlisted loopback
  Origin can use the local voice vault. Firebase/cloud rollout is a separate gate.
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
