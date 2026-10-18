# Data, consent and release boundaries

[Overview](../README.md) · [Architecture](ARCHITECTURE.md) ·
[Configuration](DEVELOPMENT.md)

## What this demo is—and is not

The approved hosted demo accepts fictional family data through verified
anonymous Firebase sessions. Standard voice and an adult's explicitly consented
own voice are supported. Public admission is not real-family enrollment, proof
of who is speaking or permission to activate production intake.

HugBack is not an emergency, medical, monitoring or money-transfer service.
It names itself as HugBack, answers direct identity questions honestly and never
claims to be the child or a human family member. Production telephone disclosure
and consent wording require a separate review.

Imported chats, call audio, transcripts and model output are private untrusted
data—not instructions or authorization. Never use real family material in
source control, examples, tests, demonstrations or screenshots.

## Consent is not one switch

| Permission | What it allows | What it does not allow |
| --- | --- | --- |
| Simulated family setup | Fictional recipient setup within the current owner scope. | Real identity, family relationship or phone enrollment. |
| Simulated dual-participant background permission | Bounded reviewed fictional excerpts as context. | Full original upload, unrestricted recall or real-family activation. |
| Recipient-specific memory permission | Bounded eligible cross-call wellbeing follow-ups. | Summary sharing, diagnosis or another recipient's memories. |
| Separate summary-sharing permission | Short summaries for future calls, plus a bounded continuity recap. | Raw transcript access or retroactive reconstruction of discarded turns. |
| Separate wellbeing-signal permission | A bounded AI-estimated, non-medical call signal. | Medical conclusions, emergency monitoring or private reasoning. |
| Separate topic-notice permission | Bounded topic-triggered notification behavior when separately configured. | Sending excerpts, transcripts or medical conclusions. |
| Adult own-voice + spoken consent + Google/billing acknowledgement | Explicit voice enrollment and subsequent authorized TTS. | Impersonation, verified likeness or arbitrary third-party voice cloning. |

Real parent calls require verified enrollment and standing,
recipient-specific sharing consent. Imported-chat and memory consent do not
grant call-summary sharing. There is no per-call approval in the current
standing-summary design. Revocation blocks reads and erases saved summaries and
any previously retained test turns.

Current fictional calls save no new raw turns for child history. An older
fictional call that already has text may be converted only by an explicit paid
operator action; raw text is erased after success. Other old calls remain
unavailable. Private Critic reports never become child summaries.

## Isolation and access

- One adult-child voice owner can have multiple independent recipients. Every
  context mutation/call requires a server-issued recipient selector validated
  against token-derived ownership, membership, revision and current consent.
- Remote and public access flags are separate and off by default. Hosted mode
  also requires a verified token, exact HTTPS Origin and named synthetic
  Firestore. CORS, a UUID, an email, a URL or a role selector is not identity.
- Direct browser Firestore access must be denied. Check the actual database's
  rules for overlapping permissive matches. Backend server SDKs use IAM and
  bypass client rules, so backend credentials also require least privilege.
- Losing the browser's anonymous identity has no implemented recovery/linking
  flow. Never reassign another owner's records to work around that limit.
- A publicly reachable demo has no implied invitation restriction or global
  quota. Billing alerts and per-call limits are not a hard spending cap.

## Voice handling

Enrollment requires an adult own-voice sample, separate spoken consent and an
explicit acknowledgement before Google upload. File selection, page load and
call start never implicitly upload a recording. Enrollment makes a bounded
provider request without automatic retry; an unknown result is not permission
to retry a potentially billable upload silently.

The app retains **keys and metadata, not recordings**. Firestore mode uses a
separate backend-only vault collection in the same named database. Local mode
uses a private SQLite test vault. No SQLite fallback or silent migration is
allowed. Browsers receive profile metadata only, never provider keys.

Firestore transactions and a 120-second enrollment lease fence concurrent or
late responses across instances. A new profile must be enabled and assigned
explicitly per recipient. Replacement, disablement and expiry invalidate stale
assignments; no automatic standard-voice fallback.

Keys become unusable after the earlier of provider expiry or seven days.
Expiry is enforced on use; clearing expired keys on successful access is not
a scheduled purge. Removal deletes the saved profile/key, not Google's issued
key or provider retention, and does not terminate an already active call.
End active calls before changing/removing their voice.

Firestore offers managed encryption at rest, not a separate application-level
secret encryption scheme. Authorized backend/database administrators can read
keys. `store=False` is not a promise about all Google processing or retention.
Provider entitlement, likeness and acoustic quality require separate validation.

## Retention and deletion limits

| Data | Current boundary |
| --- | --- |
| Synthetic families | Seven-day access expiry. SQLite purges on access; Firestore access expiry is not a provisioned TTL/physical cleanup job. |
| Browser chat previews | Owner/recipient-scoped, bounded and expired on later access—not while the browser is closed. |
| Synthetic call history | Bounded call records and optional summaries; no new raw turns for sharing. |
| Canonical wellbeing concerns | Default 72-hour retention/eligibility, cleanup on access; not guaranteed exact-time physical purge. |
| Wellbeing signals | Bounded, short-lived estimates; no audio, transcript or model reasoning retained by that path. |
| Voice recordings | Transient app memory and explicit Google processing only; no persisted recordings in the app vault. |
| Retained original imports | Separate private GCS objects; no upload-triggered deletion or automatic TTL. Authorized erasure remains a gated workflow. |

Turning a feature flag off or switching storage is not migration or erasure.
In-flight model responses are subject to consent-generation checks so stale
work cannot silently restore revoked data. Dormant-record cleanup, complete
provider/backup erasure and production deletion verification remain release
work—not promises made by this demo.

## Optional email

The code supports a bounded saved-summary email and a separate brief topic
notice. The authenticated owner may submit the demo family destination to the
backend; responses expose only a masked hint. This is not verified production
child-email enrollment. Summary email contains only the already-generated
bounded summary; topic notices contain no transcript, excerpt or medical
conclusion. Browser input is never authority over another family's destination.

SMTP is off by default. Sender credentials belong only on the backend. Failed,
unconfigured and provider-accepted states must be reported accurately;
“accepted” does not prove inbox delivery. There is no durable email retry queue.
Tests mock SMTP. This cleanup authorizes no send or SMTP enablement. Real
automatic notices still require verified child email and separate standing
parent permission.

## Separate internal original-intake module

This is **not** a browser upload API or identity verifier. A trusted operator
must resolve Forms/Drive submissions to stable owner/recipient IDs. Form fields,
phone numbers, filenames and browser IDs cannot establish that authority.
Automatic Forms/Drive pickup and production enrollment are not implemented.

The [intake CLI](../backend/scripts/import_chat_original.py) defaults to offline
validation. See [the safe fixture command](TESTING.md#optional-emulator-and-operator-checks).
Actual storage requires existing authorized resources, `CLOUD_INTAKE_ENABLED`,
`FIRESTORE_ENABLED`, `CLOUD_IMPORT_BUCKET` and **both** `--execute` and
`--acknowledge-cloud-storage`. Never enable this path in synthetic Firestore
mode. Upload acknowledgement is not consent for model use.

Storage preserves exact original bytes in a private GCS object; Firestore holds
recipient-scoped metadata and bounded inactive candidates. Requirements:

- Uniform bucket-level access, enforced public-access prevention and no
  lifecycle `Delete` rule. This adapter accepts bucket names without dots.
- Narrow backend IAM: bucket metadata read, object create/read, not overwrite,
  delete or access administration; audit inherited grants too.
- Deny direct browser access. The [Firestore](../backend/deploy/examples/firestore.rules)
  and [Storage](../backend/deploy/examples/storage.rules) rules are undeployed
  examples for a dedicated setup, not proof of live enforcement.
- Conditional object creation plus stored generation, size and SHA-256 checks;
  no public URL, signed URL or browser download token.
- Retry with the same owner, recipient request ID, filename, attribution mapping
  and bytes. `upload_pending` may mean an object exists but completion is not
  confirmed. Do not treat it as success or overwrite it. A pending reservation
  consumes a slot; no cleanup worker is included.
- Current bounds: eight recipients per owner, 100 reserved imports per
  recipient, 1 MiB per file and 2,000 messages. Imports are not deduplicated
  across recipients/families. Changed mapping/filename creates another import.

Originals are retained after processing; neither the GCS object nor the Drive
source is deleted by upload. This is not immutable storage: an authorized
erasure workflow must cover both copies, metadata, derived state and stale
retry tombstones. That workflow, backup/soft-delete review and verification
remain gated. Review never alters the original or activates call context.
Bucket changes do not migrate imports; failures do not fall back to SQLite.

## Before a real-family release

Required work includes trusted identity/enrollment, verified participant
permissions and revocation, telephone disclosure/PSTN integration, real cloud
rules/IAM tests, managed secrets, durable processing and delivery, complete
deletion, provider-quality evaluation and operational cost controls.
Google provides AI and data processing; any future non-Google telephony carrier
must stay behind an adapter. Do not infer production readiness from an offline
test pass or a configuration-only health response.
