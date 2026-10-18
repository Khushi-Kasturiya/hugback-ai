# Development and configuration

[Shared quickstart](../README.md#run-locally) · [Tests](TESTING.md) ·
[Safety](DATA_AND_SAFETY.md)

Run backend commands from `backend/` and frontend commands from `frontend/`.
Python 3.11+ and Node.js 20 LTS match the supported source/runtime baseline.
No new cloud resources are needed for local setup or mocked tests.

## Local backend profile

The backend reads its private `backend/.env` through Pydantic Settings; process
environment variables take precedence. There is intentionally no checked-in
backend `.env` or deployment secret profile. For a **new local checkout**, this
is a safe synthetic setup profile:

```dotenv
HOST=127.0.0.1
PORT=8000
CORS_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
LOCAL_DEMO_ENABLED=TRUE
HUGBACK_AUTH_MODE=development
HUGBACK_DEMO_STORE=sqlite
HUGBACK_LIVE_VOICE_MODE=preset
HUGBACK_WORKFLOW_ENABLED=FALSE
HUGBACK_CONTEXT_EXTRACTION_ENABLED=FALSE
HUGBACK_REPLICATED_TTS_ENABLED=FALSE
HUGBACK_CLOUD_TEST_ENABLED=FALSE
HUGBACK_REMOTE_TEST_ENABLED=FALSE
HUGBACK_PUBLIC_DEMO_ENABLED=FALSE
HUGBACK_JUDGE_DEMO_ENABLED=FALSE
HUGBACK_ALERT_EMAIL_ENABLED=FALSE
FIRESTORE_ENABLED=FALSE
MEMORY_ENABLED=FALSE
FOLLOWUPS_ENABLED=FALSE
CLOUD_INTAKE_ENABLED=FALSE
PORTAL_SHARING_ENABLED=FALSE
```

Leave `FIRESTORE_EMULATOR_HOST` unset in both the shell and `.env`. Do not replace
an existing private profile with this block or copy deployed credentials into a
test checkout. Treat inherited shell settings as configuration too.

After installing dependencies, run `.venv/bin/python -m app.main` or `bash run.sh`.
`run.sh` selects `.venv` when available and honors `HOST`/`PORT`.
Inspect [settings](../backend/app/config.py) for the complete validated options.

### Optional Google-backed capabilities

These are **not needed by offline tests**. Configure them only for an authorized
synthetic model run, with a server-only `GEMINI_API_KEY`:

| Setting | Meaning |
| --- | --- |
| `HUGBACK_MODEL` / `HUGBACK_VOICE_NAME` | Live model and preset voice. |
| `HUGBACK_WORKFLOW_ENABLED=TRUE` | Adds the bounded Planner/Critic workflow; browser acknowledgement is also required. |
| `HUGBACK_CONTEXT_EXTRACTION_ENABLED=TRUE` | Structured extraction of source-linked fictional background. |
| `FOLLOWUP_EXTRACTION_MODEL` | Structured memory/specialist model setting. |
| `HUGBACK_CALL_SUMMARY_MODEL` | Separately configured short-summary model. |
| `HUGBACK_REPLICATED_TTS_ENABLED=TRUE` / `HUGBACK_TTS_MODEL` | Exposes explicitly consented adult own-voice enrollment and TTS. |
| `HUGBACK_END_OF_SPEECH_SILENCE_MS` | End-of-turn silence, 700–1600 ms; default 1300. More pause tolerance can add latency. |
| `HUGBACK_TTS_FIRST_PHRASE_CHARS` / `HUGBACK_TTS_LOOKAHEAD` | Bounded initial phrase and at most one phrase of synthesis lookahead; `0` disables lookahead. Interrupted synthesis may still cost money. |

Use model IDs available to your authorized project; defaults are not a guarantee
of entitlement. Turning the workflow off does not make Live, TTS or extraction
free. Custom voice still uses `HUGBACK_LIVE_VOICE_MODE=preset`: its selected
profile is routed through separate TTS, not the experimental inline-voice mode.

## Frontend environment

Copy [the local example](../frontend/.env.example) to `.env.local` without
overwriting existing settings. Use HTTP and WebSocket endpoints for the **same**
backend:

```dotenv
NEXT_PUBLIC_HUGBACK_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_HUGBACK_WS_URL=ws://127.0.0.1:8000/ws
NEXT_PUBLIC_HUGBACK_DEMO_MODE=true
NEXT_PUBLIC_FIREBASE_API_KEY=
```

The explicitly empty Firebase key keeps local development identity selected,
including a local build that would otherwise inherit `.env.production`.
For an authorized Firebase test, use that project's public **Firebase Web API
key**, not a Gemini key or service-account credential.

`NEXT_PUBLIC_*` values are embedded at **build time**. Restart development after
changing them; rebuild a production image to change browser configuration.
The committed `.env.production` points at the existing hosted backend. Docker
excludes `.env*.local`; local loopback overlays are not deployed by that image.
No frontend flag can authorize backend access.

Keep a consistent browser/origin. `localhost`, `127.0.0.1`, private browsing and
different devices can have different identities. Refresh failures must not
silently replace the UID. Do not copy someone else's tokens to recover data.

## Storage modes

| Requirement | Local SQLite | Loopback emulator | Existing live test Firestore |
| --- | --- | --- | --- |
| `HUGBACK_DEMO_STORE` | `sqlite` | `firestore` | `firestore` |
| `FIRESTORE_ENABLED` | `FALSE` | `TRUE` | `TRUE` |
| `HUGBACK_AUTH_MODE` | `development` | `development` | `firebase` |
| Project / database | Not used | `demo-hugback` / named test DB | Matching Firebase project / dedicated named DB |
| `FIRESTORE_EMULATOR_HOST` | Unset | `127.0.0.1:8080` | Unset |
| `HUGBACK_CLOUD_TEST_ENABLED` | `FALSE` | `FALSE` | Explicitly `TRUE` |
| Operator UID list | Not used | Not used | Required unless separately approved public admission is enabled |

All three require `LOCAL_DEMO_ENABLED=TRUE`. This flag means synthetic mode,
not that all storage is local. In Firestore mode, keep `MEMORY_ENABLED`,
`FOLLOWUPS_ENABLED`, `CLOUD_INTAKE_ENABLED` and `PORTAL_SHARING_ENABLED` false.
There is no SQLite fallback or implicit migration when a store fails.

The emulator configuration is [firebase.synthetic.json](../backend/firebase.synthetic.json).
With an already-installed compatible Firebase CLI/Java runtime:

```sh
firebase emulators:start --only firestore \
  --project demo-hugback --config firebase.synthetic.json
```

Set `HUGBACK_DEMO_PROJECT=demo-hugback` and
`HUGBACK_DEMO_DATABASE=hugback-synthetic` for that local profile. Real model
requests are not emulated. For live storage, backend ADC/service identity and
IAM authorize Firestore; a Gemini key or browser token does not replace them.

## Deployment review—not a deployment recipe

This submission repository is independent of the source repositories connected
to the deployed services. Keep frontend/backend as separate build contexts if
an operator later migrates deployment here.

Important existing build behavior:

- **Backend Docker needs a private `.env` in its build context.** The Dockerfile
  copies it into the image and intentionally fails if absent. There is **no
  example-file fallback**. A clean Git clone alone cannot build that deployment
  image. Do not create a fake profile just to make a deployment appear valid.
- Embedding credentials in the image is a hackathon-only shortcut, not
  production-grade secret management. Image/source-upload readers may see them.
  Keep the file untracked; review access and credential rotation. Moving to
  managed secrets is a separate release change.
- The package description is inline in `pyproject.toml`, so removing the
  duplicate backend README does not add a parent-directory build dependency.
- The frontend uses standalone Next output; both containers listen on 8080.
  Review Cloud Run WebSocket timeout and instance/concurrency behavior separately.

Before any separately authorized hosted release, verify:

1. Matching Firebase token verification and a dedicated named Firestore DB with
   backend IAM; no production/legacy data flags or emulator routing.
2. `HUGBACK_REMOTE_TEST_ENABLED`, one exact HTTPS
   `HUGBACK_REMOTE_TEST_ORIGIN` also listed in `CORS_ORIGINS`, and the separate
   `HUGBACK_PUBLIC_DEMO_ENABLED` gate if public admission is intended.
   `HUGBACK_JUDGE_DEMO_ENABLED` additionally requires both remote/public gates.
3. Deny-all browser rules on the **actual named DB**, without overlapping allow
   rules, before enabling `HUGBACK_FIRESTORE_VOICE_RULES_CONFIRMED`. The flag is
   an operator attestation, not an automatic audit.
4. Frontend API/WS/Firebase public values baked into the intended image.
   Review costs: public admission has no global spending cap.
5. Email remains disabled unless separately authorized. Code supports a
   family-scoped destination, server-only SMTP credentials and bounded summary
   delivery; neither documentation nor tests authorize enabling it.
6. Review branches are merged before an independently requested deployment.
   Check existing automatic triggers before merge; do not assume merge is inert.

Health/architecture manifests report settings, not a successful cloud probe.
Any live save/reload, voice upload, call, email or cloud-write check requires
its own authorization and fictional test data.
