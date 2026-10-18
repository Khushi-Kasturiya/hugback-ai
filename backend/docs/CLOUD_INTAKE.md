# Retained chat originals — internal no-app intake

## What is implemented

The product stays **Forms/Drive → backend → ordinary telephone**. No cloud child
dashboard or new public upload API is part of this change.

`app/family/` provides the storage sink for a future trusted Forms/Drive worker:

1. Resolve a stable owner and intended recipient from a **trusted registry**.
   The operator command below supplies that mapping explicitly. It does not
   authenticate the child, verify a phone, or connect family accounts.
2. Validate a bounded UTF-8 one-to-one export with declared date order, timezone
   and both participant labels. Validation happens before storage writes.
3. Transactionally reserve an import in Firestore, under one recipient.
4. Store the **exact original bytes** in an existing private Google Cloud
   Storage bucket, with conditional create (`if_generation_match=0`).
5. Commit its object generation, SHA-256, size and parser version in Firestore.
   Full exports are never stored in Firestore. Original BOM/line endings survive.
6. Optional internal review selects source indexes from a server reparse: up to
   eight excerpts of at most 500 characters each. These are **inactive candidates**,
   not extracted facts, participant approvals or call memory.

No call/model request is made. No new route is mounted in the existing web server.
The source file and original Drive upload are never deleted by this module.

## Data layout

```text
Firestore
cloud_families/{server-derived-family-id}
  ownerId, schemaVersion, createdAt, recipientLabels
  /recipients/{server-derived-recipient-id}
    label, relationship, phone, timeZone, language, setupHash, importCount
    /imports/{content-and-mapping-hash}
      status: upload_pending | stored
      sha256, size, generation, bucket, objectPath, parserVersion
      filename, participant labels, date order, timezone, messageCount
      revision, candidateExcerpts[], reviewSha256, reviewedAt

Cloud Storage — not public
families/{familyId}/recipients/{recipientId}/imports/{importId}/original
```

Owner and recipient are not inferred from a voice, number, filename or browser
role. Use one owner ID per family and a different stable recipient request UUID
for Mother/Father; reuse both IDs on retries. This is scope separation, **not**
proof that a person belongs to a family. The caller is a trusted worker/operator.
The current sink caps eight recipients per owner, 100 reserved imports per
recipient, 1 MiB per export and 2,000 messages. It does not deduplicate across
families/recipients or share their review/consent.

Original reads are internal authenticated SDK calls, pinned to the saved
generation and checked against size and SHA-256. No public URL, signed URL,
Firebase download token, browser file store or token-bearing query string is
generated. Review never changes the original object.

## Safe offline check — no credentials or network needed

From the backend checkout:

```sh
.venv/bin/python scripts/import_chat_original.py \
  --manifest docs/examples/synthetic-intake.json \
  --file docs/examples/synthetic-chat.txt
```

This prints only validation counts, `cloudAccessed: false` and
`contextActive: false`. It validates even if cloud flags are enabled, because
`--execute` is required for all cloud access. The two checked-in example files
contain only fictional data.

Real manifests and exports belong outside source control. `.private-intake/` is
also gitignored and excluded from Docker context as a defense in depth. Never
paste private content/phone numbers into test fixtures, logs, screenshots or
command arguments. Do not reuse the fictional IDs for real enrollment.

The manifest is **operator-owned**, not an untrusted Google Form response.
`acknowledgeSetup` and `acknowledgeUpload` acknowledge storage only. Participant
labels are declared attribution, not verified speaker identity. A Form's email,
phone or supplied owner ID must not be treated as authorization.

## Operator setup — not performed by this implementation

Before any authorized cloud test:

- Select an existing Google Cloud project, Firestore database, dedicated bucket
  and approved region. No command here creates any resource or enables billing.
- Review Google billing and data terms. Cloud Storage and Firestore have separate
  usage/region-based charges; free allowances are **not** a zero-cost guarantee.
  Budget alerts are not a spending cap.
  [Cloud Storage pricing](https://cloud.google.com/storage/pricing),
  [Firestore pricing](https://cloud.google.com/firestore/pricing).
- Require uniform bucket-level access, bucket-level public access prevention
  explicitly set to `enforced`, and **no lifecycle `Delete` rule**. The adapter
  checks these before object operations. For this initial implementation use
  a 3–63-character bucket name without dots. It fails closed otherwise.
  [Public access prevention](https://cloud.google.com/storage/docs/public-access-prevention),
  [uniform bucket-level access](https://cloud.google.com/storage/docs/uniform-bucket-level-access).
- Scope the intake service account to the dedicated resources. Storage needs
  `storage.buckets.get`, `storage.objects.create` and `storage.objects.get`;
  it does not need delete, overwrite, public access or IAM administration.
  Public access prevention does not restrict every authenticated principal:
  separately audit IAM and inherited grants.
  [Storage IAM permissions](https://cloud.google.com/storage/docs/access-control/iam-permissions).
- Firestore server SDKs use IAM, not Firebase client rules. Restrict the worker's
  database access and consider a dedicated database/project; owner path checks
  do not constrain a compromised server credential. Client access to these
  private collections must be denied. The supplied rules are **undeployed**
  deny-all examples for a dedicated setup, not a drop-in replacement for a
  project's existing rules. Overlapping permissive matches can override a
  narrow deny. [Firestore server security](https://cloud.google.com/firestore/native/docs/security/iam).
- Use ADC/workload identity or another approved service-account setup. Never put
  credentials in a Form, frontend, manifest or source control. No Firebase
  anonymous session is needed by this server-only module.
- Restrict Drive folder/Form access and define authenticated submission routing
  before automation. The worker must map the submission to the trusted
  family/recipient registry; automatically trusting respondent-supplied IDs is
  not implemented or authorized.

Only after authorization, configure the operator job (not the browser):

```dotenv
CLOUD_INTAKE_ENABLED=True
FIRESTORE_ENABLED=True
FIREBASE_PROJECT_ID=your-approved-existing-project
FIRESTORE_DATABASE=(default)
CLOUD_IMPORT_BUCKET=your-approved-private-import-bucket
```

Leave other memory/call flags off for an intake test. Enabling Firestore alone
does not upload a file. The command requires **both** `--execute` and
`--acknowledge-cloud-storage` to use the configured resources. Those switches
acknowledge retention, authorized upload and possible charges; they do not
establish participant consent for model processing or conversation use.

## Retention and uncertain operations

- Originals have **no application TTL or delete-after-processing step**.
  The backend does not enable a bucket lock, immutable legal hold or irrevocable
  storage. An authorized erasure request remains possible in the product design.
- Copying from Drive leaves two private copies. This code deletes neither.
  Any later deletion worker must cover Drive, objects, metadata and derived
  records, with tombstones to stop stale retries resurrecting data. That worker,
  backups/soft-delete policy and complete deletion verification remain gates.
- `upload_pending` means completion was not confirmed: the object may be absent
  or already saved while the Firestore completion write failed. It is not shown
  as successfully retained until the completion record is committed.
- Retry with the **same** owner UUID, recipient request UUID, filename, mapping
  and original bytes. A retry resumes the reservation without another quota
  charge or overwrite; recovery checks the existing object's exact bytes.
  Changed mapping/filename creates a different import, not an update.
- A pending reservation consumes one import slot until resolved. There is no
  cleanup/reconciliation worker or deletion API in this slice.
- Changing buckets does not silently move imports. The service rejects access
  to an import recorded in a different configured bucket.
- Saving a changed candidate selection checks the previous revision. Reparse
  refuses an unsupported saved parser version; original retrieval still works.
- Cloud failures are not silently saved to SQLite/IndexedDB. Logs/command output
  do not expose source text or provider error bodies.

## What still requires implementation and validation

- Automatic restricted Forms/Drive pickup, stable submission registry and
  production owner/family verification.
- DLP/redaction, Gemini structured extraction and validated source-backed facts.
- Verified enrollment, each participant's exact-scope consent, revocation and a
  telephone adapter that resolves the actual recipient. Nothing in this storage
  module can activate call context, even if a record contains approval-like fields.
- Durable worker dispatch/reconciliation, rate limits, cloud emulator/live
  contract tests, IAM/rules validation, operational monitoring and deletion.
- Cloud voice enrollment, recap/email delivery, and any migration of local demo
  identities, synthetic memory or local voice keys.

Local mocked tests prove code behavior, not deployed IAM, real cloud availability,
provider retention guarantees, verified identity or production readiness.
