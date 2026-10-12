# Child portal boundaries

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
