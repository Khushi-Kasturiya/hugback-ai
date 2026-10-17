# Hosted synthetic demo — release review, 18 October 2026

The user approved open demo admission for judges: visitors use the same URL,
sign in anonymously through Firebase, and do **not** need invitations or manual
UID approval. This is a fictional-data, standard-voice demo, not real-family
identity verification, consent/enrollment or a telephone-service release.

## Why the current deployed site reports “Local demo mode is disabled”

The read-only production health check on 18 October reported `caller_auth=firebase`,
`demo_storage=sqlite`, `firestore_configured=false`, and `workflow_enabled=false`.
Local `.env` edits do not change Cloud Run. The former loopback-only gate also
blocked remote requests regardless of CORS or Firebase configuration.

This branch adds an explicit remote access gate and a separate public admission
flag. The existing local/restricted modes retain their restrictions by default.
**The code and reference configuration are not evidence of deployment.**

## Settings to apply when deployment is authorized

Use `.env.cloud-run.example` as a secret-free reference, not as a credentials file
or a `gcloud --env-vars-file` input (that flag expects YAML, not dotenv syntax).
The existing project is `project-84a7c715-3d60-4253-acb`; the existing dedicated
named database is `hugback-synthetic` in `us-central1`.

Required hosted-demo settings:

```dotenv
LOCAL_DEMO_ENABLED=TRUE
HUGBACK_DEMO_STORE=firestore
FIRESTORE_ENABLED=TRUE
HUGBACK_DEMO_PROJECT=project-84a7c715-3d60-4253-acb
HUGBACK_DEMO_DATABASE=hugback-synthetic
HUGBACK_AUTH_MODE=firebase
FIREBASE_PROJECT_ID=project-84a7c715-3d60-4253-acb
HUGBACK_CLOUD_TEST_ENABLED=TRUE
HUGBACK_REMOTE_TEST_ENABLED=TRUE
HUGBACK_REMOTE_TEST_ORIGIN=https://hugback.cloud.run
CORS_ORIGINS=https://hugback.cloud.run
HUGBACK_PUBLIC_DEMO_ENABLED=TRUE
HUGBACK_WORKFLOW_ENABLED=TRUE
HUGBACK_LIVE_VOICE_MODE=preset
HUGBACK_REPLICATED_TTS_ENABLED=TRUE
# Set only after verifying deny-all browser rules on the named database:
HUGBACK_FIRESTORE_VOICE_RULES_CONFIRMED=TRUE
HUGBACK_ALERT_EMAIL_ENABLED=FALSE
MEMORY_ENABLED=FALSE
FOLLOWUPS_ENABLED=FALSE
CLOUD_INTAKE_ENABLED=FALSE
PORTAL_SHARING_ENABLED=FALSE
```

- `HUGBACK_TEST_OWNER_UIDS` is not required in public-demo mode. With public
  admission off, remote mode requires the explicit raw-UID list again. Merely
  knowing a UID never authenticates a request.
- Keep `FIRESTORE_EMULATOR_HOST` unset. Do not put personal ADC/service-account
  JSON in Cloud Run. The attached service identity must have access to the
  existing named database. Server SDK calls use IAM, not client Firestore rules.
- Supply the backend Gemini credential via the existing secure secret setup;
  never commit it or put it in a `NEXT_PUBLIC_*` variable. Rotate any credentials
  previously disclosed outside their intended secret store before deployment.
- Frontend `.env.production` selects the existing HTTPS/WSS backend and
  `NEXT_PUBLIC_HUGBACK_DEMO_MODE=true`. This ensures calls carry the selected
  recipient and workflow acknowledgement. The non-demo path is rejected by
  named Firestore mode. Firebase Anonymous Authentication must be enabled.
- Next.js public settings are embedded at **build time**. Rebuild the frontend
  image; runtime changes alone do not replace its JavaScript configuration.
  `.env*.local` is excluded from Docker. Local testing still uses its private
  loopback overlay; no browser credentials or local records are migrated.
- The existing backend image listens on port 8080. Cloud Run WebSocket request
  timeout and instance/concurrency settings need deliberate review at deployment.

## What remains enforced

Every portal, family and call entry point requires a verified Firebase ID token,
the exact configured HTTPS Origin, and the explicit named-database test mode.
A browser's development UUID, arbitrary `userId`, forwarded header, Origin alone,
or knowledge of the URL cannot impersonate another visitor. All family and call
selectors remain checked against the token-derived owner, recipient membership,
revision, active lease and simulated consent generations. No SQLite fallback.
Missing Origin is rejected even for remote reads. Invalid configuration fails
startup/entry checks rather than silently relaxing authentication.

Public admission intentionally permits **any** visitor with a valid Firebase
identity from this project; URL secrecy is not access control. A forwarded link
can be used by someone other than a judge. Existing ten-minute call limits and
recipient leases are not a global quota or spending cap. No new quotas or cost
optimization are introduced in this change, as requested. Review provider quotas
and monitor billing before enabling; billing alerts alone do not cap spending.

## Scope limits that must stay visible

- Both standard and consented adult child voice are supported. Family state and
  temporary child keys use the same named Firestore database, separate collections.
  Standard voice needs no custom key. Verify `firestore.synthetic.rules` on the
  named DB, with no overlapping browser allow rules, and backend-only IAM before
  enabling `HUGBACK_FIRESTORE_VOICE_RULES_CONFIRMED`. The reference env deliberately
  leaves this false so copying it alone cannot enable private key writes.
- The private vault persists only keys/profile metadata and 120-second enrollment
  leases; never audio. Transactions fence concurrent/late responses across Cloud
  Run instances. No local fallback or automatic migration. Expiry is enforced on
  every use; expired keys clear on successful access, not a scheduled purge.
  Removal does not revoke the Google key or terminate an already active call.
- Synthetic family data only. Real-family consent, verified enrollment, retained
  original intake, production sharing and phone-call release are not enabled.
- Post-call reconciliation, Critic and summaries remain process-local best effort.
  Instance replacement can lose in-flight work; configure CPU/lifecycle accordingly
  and do not promise durable summaries. `MEMORY_PROCESSING_MODE=cloud_tasks` only
  handles the legacy path and does not fix synthetic finalization.
- SMTP is disabled. No email, voice upload or paid call is part of offline tests.
- Provider model IDs in the reference file are existing configured IDs, not a
  new claim of entitlement or measured latency/voice quality.

## Merge, deploy and verify

Read-only check on 18 October: the Firebase Rules API returned HTTP 403 with
reason `SERVICE_DISABLED` for `firebaserules.googleapis.com` when reading the
release `cloud.firestore/hugback-synthetic` in the shared project. This is not
evidence of permissive rules or a Firestore data-connectivity failure; the live
rules could not be inspected. No API was enabled and no rules were changed.
Before voice enrollment, an authorized operator must enable access to the Rules
API as needed, inspect/apply the deny-all rules on **hugback-synthetic**, and
verify browser-token reads/writes are denied (including the private voice
collection). Only then set the rules-confirmation flag. Do not simply enable
the flag to bypass this unresolved verification.

The requested workflow is branches/PRs first, operator merge into `main`, then a
separately requested deployment of the merged revisions. If a Cloud Build trigger
already deploys automatically on main, merging may deploy immediately: verify
that trigger before merging rather than assuming a manual-only deployment.

Offline checks cover configuration rejection, new anonymous visitor admission,
unknown UID denial in restricted mode, exact/missing/forged Origin rejection,
invalid token rejection, owner/recipient isolation, standard WebSocket readiness,
child-voice readiness, private-key redaction, owner isolation, multi-instance
enrollment races, stale/expired/replaced key denial, no SQLite fallback,
legacy-path denial, existing memory privacy and audio latency regressions.
Provider verification and storage are mocked. Final counts belong in the PRs.

18 October final offline run: backend `unittest discover` ran 377 tests
(376 passed, 1 opt-in emulator test skipped); frontend 93 tests, TypeScript
typecheck and isolated Next production build passed. The isolated frontend
build used the existing lockfile with a clean dependency install, without
changing the working app's dependencies. These checks are not live Firebase
rules/IAM tests, voice uploads or paid latency/likeness verification.

After an authorized deployment: verify reported settings, use a fresh browser
session to confirm no manual UID approval is required, create/reload fictional
state, confirm a second visitor cannot read it, and only with paid opt-in perform
a standard-voice call and an explicitly consented child-voice enrollment/call. Do not call a configuration-only health response a Firestore
connectivity test. No cloud settings or resources are changed by this document.
