# Child portal boundaries

- 18 October hosted synthetic demo: explicit remote + public-demo mode admits
  verified anonymous Firebase visitors without a pre-known UID. Preserve
  per-owner isolation and exact HTTPS Origin; no real identity/relationship
  grant is implied. This narrowly supersedes the loopback-only rule below.
  Both voices are supported. Firestore mode uses the backend-only Firestore
  voice vault, never the single-machine adapter. Return metadata only, not keys.
  Explicit own-voice/spoken consent and Google billing acknowledgement remain.

- 13 October: product direction is date-filtered short call summaries after
  verified, recipient-specific standing parent consent, without per-call approval.
  The existing production mailbox reader is legacy and does not provide this.
  Synthetic demo history lives in `app/demo` behind its own test identity and
  simulated consent; it cannot be used as a verified real-parent summary API.
  The synthetic summary route never returns raw turns. This supersedes the
  blanket recap ban below only for this scoped design.

- Current product is no-app: ordinary telephone calls and Forms/Drive intake.
  `/childportal` is existing internal prototype tooling, not product enrollment.
- Reuse Firebase anonymous authentication; there is no email/password screen.
  A development UUID is not authentication and must never read private cloud data.
- The child UID is not the parent UID. Only a trusted enrollment process can
  write a verified relationship; the public portal cannot grant consent.
- Never return a transcript, private continuity memory, or unapproved summary.
  Summary sharing requires exact-text approval, named child UID, expiration,
  and a current relationship generation. Fail closed on malformed records.
- Cloud family storage belongs to the internal Forms/Drive intake module.
  Do not expose it through this portal or accept a browser-selected family as
  verified enrollment. Retained uploads never activate call context.
- Exception: the user-approved local synthetic simulator in `app/demo` can
  activate explicitly reviewed fictional excerpts. Its simulated permissions
  never grant real consent, change this mailbox reader, or access cloud records.
  Recap sharing is excluded from steps 1–5 of the demo.
- Approved 12 October: the synthetic simulator can also use a dedicated named
  Firestore test database with explicit gates and an operator Firebase UID
  allowlist. Keep loopback checks. In this mode disable the production mailbox
  reader; anonymous identity is test ownership, not verified family enrollment.
  Critic output is not a summary and must never appear in this portal.
- Do not provision resources, enable billing, send emails, make calls or upload
  private data during implementation/tests. Use synthetic fixtures.
