# Hosted synthetic demo — release review, 18 October 2026

The user approved open demo admission for judges: visitors use the same URL,
sign in anonymously through Firebase, and do **not** need invitations or manual
UID approval. This is a fictional-data demo with standard and explicitly
consented adult child-voice options, not real-family
identity verification, consent/enrollment or a telephone-service release.

## Current deployed revision versus this release profile

An earlier production health check on 18 October reported the old disabled
profile. A later read-only Cloud Run inspection showed generation 8 now has
Firebase auth, named Firestore, the four-stage workflow, public remote demo and
replicated TTS enabled, including the voice-rules confirmation. It does not set
`HUGBACK_CONTEXT_EXTRACTION_ENABLED` or `HUGBACK_JUDGE_DEMO_ENABLED`; those two
capabilities are enabled in this repository's release profile and still require
a backend deployment. Summary email also requires the new backend revision and
SMTP credentials. Under the approved hackathon shortcut, changes to the private
`.env` reach Cloud Run only after rebuilding and deploying from this local source
directory; they do not modify an already-running revision.

This branch adds an explicit remote access gate and a separate public admission
flag. The existing local/restricted modes retain their restrictions by default.
**The code and reference configuration are not evidence of deployment.**

## Settings to apply when deployment is authorized

Use `.env.cloud-run.example` as a secret-free reference. For this hackathon, the
user explicitly chose the private Git-ignored `.env` as the Cloud Run container's
runtime profile instead of Secret Manager. `.gcloudignore` includes `.env` in a
local source deployment and Docker copies it into the image. This exposes secrets
to anyone who can inspect the source upload or image and must not be described as
a production-grade secret-management design. A Git-based build will not receive
the ignored `.env` and therefore uses the safe `.env.example` fallback.
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
HUGBACK_CONTEXT_EXTRACTION_ENABLED=TRUE
HUGBACK_LIVE_VOICE_MODE=preset
HUGBACK_REPLICATED_TTS_ENABLED=TRUE
# Verified in Firebase Console on 18 October 2026 for the named database:
HUGBACK_FIRESTORE_VOICE_RULES_CONFIRMED=TRUE
HUGBACK_ALERT_EMAIL_ENABLED=TRUE
HUGBACK_PORTAL_URL=https://hugback.cloud.run/childportal
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
- For this hackathon-only local-source build, place the backend Gemini credential
  in the private `.env`; never commit it or put it in a `NEXT_PUBLIC_*` variable.
  Rotate any credential previously disclosed outside its intended store before
  deployment, then migrate it to Secret Manager after the event.
- For the hackathon-only deployment, set `HUGBACK_ALERT_SMTP_USERNAME` and
  `HUGBACK_ALERT_SMTP_APP_PASSWORD` in the private `.env` before building. The
  owner-entered destination is stored inside the authenticated family record and
  only a masked hint is returned to the browser. Rotate the app password after
  the event and migrate it to Secret Manager before broader production use.
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
  Standard voice needs no custom key. On 18 October 2026, the active rules for
  the named DB were verified in Firebase Console as a global deny-all rule with
  no overlapping browser allow rule; the repository reference therefore enables
  `HUGBACK_FIRESTORE_VOICE_RULES_CONFIRMED`. Re-verify after any rules change.
- The private vault persists only keys/profile metadata and 120-second enrollment
  leases; never audio. Transactions fence concurrent/late responses across Cloud
  Run instances. No local fallback or automatic migration. Expiry is enforced on
  every use; expired keys clear on successful access, not a scheduled purge.
  Removal does not revoke the Google key or terminate an already active call.
- Synthetic family data only. Real-family consent, verified enrollment, retained
  original intake, production sharing and phone-call release are not enabled.
- Post-call reconciliation and Critic remain process-local. Summary persistence
  and its one-time email are awaited inside the shielded WebSocket finalizer, but
  there is still no durable email retry queue after a container crash.
  `MEMORY_PROCESSING_MODE=cloud_tasks` only handles the legacy path.
- SMTP summary email is enabled in the release profile. Offline tests mock SMTP;
  they do not send email, upload a voice or place a paid call.
- Provider model IDs in the reference file are existing configured IDs, not a
  new claim of entitlement or measured latency/voice quality.

## Merge, deploy and verify

The Firebase Rules API previously returned HTTP 403 with reason
`SERVICE_DISABLED`, so the release could not be inspected through that API.
On 18 October 2026 the signed-in project owner instead inspected the active Rules
tab for **hugback-synthetic** in Firebase Console. It showed one global matcher
with `allow read, write: if false`; no overlapping browser allow rule was present.
No API was enabled and no rules were changed. Re-verify this condition after any
rules deployment before keeping the confirmation flag enabled.

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
