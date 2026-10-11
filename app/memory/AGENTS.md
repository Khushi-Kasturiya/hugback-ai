# Elara memory implementation rules

- The no-app architecture in the ELARA workspace remains authoritative.
- Firestore canonical follow-up records authorize recall. Legacy Memory Bank
  strings must not bypass consent, suppression, expiry, or deletion.
- Model output is an untrusted proposal. Validate source turn, user role, exact
  evidence, timezone-aware timestamp, scope, generation and bounds before writing.
- Model tools may neither grant consent nor select an owner/parent ID.
- In multi-recipient demos the broker supplies the membership-validated recipient
  ID as memory owner, never the family, browser or voice ID. Mother/Father have
  separate concerns, cooldowns, recovery and revocation/deletion generations.
- Keep ordinary consent, wellbeing-memory consent, imported-chat dual consent,
  and recording retention distinct. This pilot handles direct call reports only.
- A reservation is not a question asked. Generated audio is not confirmed
  playback, hearing, understanding, or an answer. An interruption is not recovery.
- Use transactions for selection and state changes; keep all network/model work
  outside transaction callbacks. Preserve revocation generations/tombstones.
- Never automatically revive a suppressed/deleted topic or a stale worker result.
- Keep raw transcripts out of the canonical pilot's persistent stores. Do not
  silently fall back to legacy persistence when the canonical store fails.
- No real family fixtures, audio, screenshots, transcript logs or provider-error
  bodies. Tests must use synthetic content and mock all cloud I/O.
- `app/demo` reuses this lifecycle through isolated local SQLite for synthetic
  role-play only. Its consent source is explicitly simulated, never a production
  grant. Google extraction in demo mode requires the local flag/development
  mode and simulated memory consent; do not loosen the production path.
- Feature flags are not permission to create cloud resources, incur charges, or
  upload private data. Keep provider/enrollment/deployment gates explicit.
