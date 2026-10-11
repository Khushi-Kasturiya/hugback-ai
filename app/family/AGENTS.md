# Internal Forms/Drive intake storage

- No public HTTP/browser interface. Use a trusted operator or service-account
  worker, explicit opt-in configuration and existing private Google resources.
  This module does not implement Forms/Drive polling or verified enrollment.
- Owner/recipient IDs must come from the operator's trusted submission registry,
  never arbitrary Form fields. IDs, filenames, chat text and model output are
  untrusted. Mother/Father imports remain isolated. No local-demo migration.
- Original bytes are immutable and retained. No upload-triggered deletion or TTL.
  Idempotent retry must preserve the original; incomplete writes remain visible.
- Bound uploads, counts, reads and candidates. No complete raw exports in
  Firestore; at most eight reviewed source excerpts may be stored. Never persist
  private chat in logs or fixtures. No public URLs or download tokens.
- Upload acknowledgement is NOT parent consent. Only a trusted enrollment producer
  can authorize a recipient and exact reviewed context. No public grant endpoint.
- No automatic AI extraction, telephone calls, summary sharing or activation
  loader in intake. Source review is candidate curation, not participant consent.
  Future activation requires trusted dual consent and verified recipient binding.
  Never wire an owner/family/voice ID as a parent's memory identity.
- Test with synthetic content and mock all Google I/O.
