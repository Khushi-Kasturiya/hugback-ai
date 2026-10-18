# Hugback: four-role end-to-end test guide

Implementation checkpoint: **13 October 2026**. This is the existing **synthetic
browser simulator**, not a parent app, production child dashboard, verified family
enrollment, or PSTN deployment. Do not use real family chats or medical histories.

## Future-call summaries in Signals back

In Family setup, select a fictional recipient and enable **Future call
summaries** with both simulated standing consents. Then make a new fictional call.
After it ends, open **Signals back**, select the same recipient, filter by call
date, and choose **View summary**. It shows one short AI-generated account of
what the parent and HugBack discussed, not raw turns. No per-call approval is
needed. Earlier fictional calls with saved text may show **Generate summary for
earlier call**; this is an explicit Google model request that may incur a charge
and erases the old saved turns after success. Other earlier calls are unavailable. A different
recipient or browser owner cannot fetch it. Turning sharing off erases summaries
and any legacy saved test text and blocks in-flight commits. New calls do not
persist raw turns for this view. The active synthetic repository may be SQLite
or explicitly selected isolated Firestore test storage; this does not activate
real phone-call history. Model failure or insufficient transcript evidence shows
summary unavailable, never raw text as fallback. Long or noisy transcriptions
are reduced to bounded in-memory excerpts before the summary request; the recap
may omit parts of a long call. Signals back now distinguishes missing speech,
oversized input, model/content failure, and interrupted processing for new calls.
An earlier unavailable call with no saved raw text cannot be reconstructed.
The summarizer is a separate Google model request during a paid browser call;
offline tests mock it.

## Optional fictional-call email notices

Enable **Future call summaries** for a fictional recipient, select and save the
test child's email in Family setup, then separately enable **Automatic topic
email**. If the role-play parent says
"I have a fever today" or reports that a close relative passed away, the
post-call finalizer records one topic event beside that call in Signals back.
Only the short summary is available there under call-summary sharing consent.
The rule reads only the role-play parent's current words; it does not diagnose,
infer an emergency or trigger from uploaded chats or HugBack's own speech.
Repeated email attempts for the same topic are suppressed for 24 hours.

SMTP is **off by default**. For an authorized fictional-mail test, use a test
Gmail account with 2-Step Verification and an app password, and confirm that
you or an expecting test recipient controls the destination mailbox. In the
private backend `.env`, set the **sender** variables:
`HUGBACK_ALERT_EMAIL_ENABLED=TRUE`, `HUGBACK_ALERT_SMTP_USERNAME`, and
`HUGBACK_ALERT_SMTP_APP_PASSWORD`. Enter the notification destination in Family
setup in either SQLite or Firestore mode. The UI shows only its masked form after
saving; Firestore keeps the raw address in the authenticated family's backend-only
record. There is no configured fallback recipient. Restart the backend. Never put the app
password in frontend files, source control or chat. The email contains a generic
notice and a link to the local portal on the test computer, not a transcript or
health claim. The local SQLite simulator stores the selected destination with
the family, without verifying real child identity. Failed/unconfigured
delivery appears accurately in Signals back. Offline tests mock SMTP and send
no email. Real family email and production delivery are not connected.

### Exact local email test, from a clean recipient

1. In the backend repository, use your existing private `.env` (copy
   `.env.example` to `.env` only if it does not exist). Keep
   `LOCAL_DEMO_ENABLED=TRUE` and `HUGBACK_DEMO_STORE=sqlite` for the local run.
   Use a Gmail account you control as the sender and an inbox held by you or
   an expecting test recipient as the destination. Put the sender's **app
   password**, not its normal Gmail password, in
   `HUGBACK_ALERT_SMTP_APP_PASSWORD`. Set the three sender variables above.
   Never post the
   `.env` or a terminal dump of it. Google documents app-password availability
   and account restrictions at
   <https://support.google.com/accounts/answer/185833>.
2. From the backend directory, run `.venv/bin/python -m app.alerts.smoke_test`.
   It prints only `ready` or `missing or off` for each gate, no secrets. A
   nonzero exit means **no email was sent**. Correct `.env` and rerun until all
   checks say `ready`. Then run
   `.venv/bin/python -m app.alerts.smoke_test --send --to YOUR_TEST_INBOX`
   to send **one generic probe** to an expecting inbox.
   Check inbox and spam. This proves SMTP acceptance/delivery for that probe,
   not that a fictional call will match the topic rule. The probe does not
   appear in Signals back because it is not a call.
3. Restart the backend after editing `.env`; refresh the child portal. In
   **Family setup**, select a fresh fictional recipient. Under **Automatic
   topic email**, enter the child's expecting test destination, check that you
   own the inbox or its owner expects this fictional notice, and click **Save
   test email for this family**. This is the only UI email field; the home-page
   early-access box has been removed. The backend stores the address in the
   private local SQLite demo family and returns only a masked hint to the UI.
   The card should say the inbox and backend sender are ready. Then enable
   **Future call summaries**. Under **Automatic topic email**, check the separate
   simulated standing permission and click **Enable future topic notices**.
   If the button says **Stop future topic emails**, that recipient already has
   notices enabled. Confirm the card says email is configured. Enabling the
   checkbox alone does not save the setting.
4. Start a **new** parent-role browser call for that same recipient. After a
   normal greeting, clearly say, “I have a fever today.” End the call. Wait a
   few seconds, then open `/childportal` → **Signals back**, select the same
   recipient, click **Refresh calls**, and inspect the newest dated call. Its
   fever notice should progress from `pending`/`sending` to `sent` if Gmail
   accepts it. Check the test inbox/spam for a **brief generic** message with
   a local portal link; it contains no quote or diagnosis. The call summary is
   generated separately and may be `unavailable` even when email is `sent`.
5. For edge cases, use another new call within 24 hours with “I have a fever
   today”: expect `suppressed` and no second email. With a fresh recipient,
   say “My neighbour has a fever; I feel fine”: expect no fever notice. With
   SMTP switched off and the backend restarted, a matching new call can show
   `not_configured` and no email. Test `failed` with mocked SMTP in
   `tests/test_alerts.py`; avoid deliberately entering a wrong password on a
   live account. A separate close-loss self-report can test `bereavement`
   using only fictional content.

The browser-selected destination is owner-scoped in both SQLite and Firestore.
A different authenticated family cannot read or use it, and API responses return
only a masked hint. Clearing or changing the address invalidates pending notices
for that family. `sent` means Gmail's SMTP server accepted the message; inbox delivery is a
separate check. `failed` means the SMTP task raised an error; its exact exception
type is in backend logs, without credentials or call text. `not_configured`
means a matched call was recorded while a required backend gate was off.
`suppressed` means an earlier pending/sending/sent notice for that recipient and
topic was within 24 hours. No row means the call was not eligible or the
detector found no supported self-report. This sender is process-local and has
no durable retry; use only for the fictional simulator.

On this machine, the live SMTP probe reached a company TLS gateway that
presented an untrusted replacement certificate for `smtp.gmail.com`. The
sender code uses `certifi` for public CA roots and **does not disable TLS
verification**. If you see `SSLCertVerificationError`, use a network that
reaches Gmail with a trusted certificate (for example a personal hotspot with
the company VPN disconnected, if company policy allows it) or ask your network
administrator for an approved trust configuration. A phone can supply its
mobile hotspot, but the backend and probe command still run on the computer.
Opening `127.0.0.1:3000` on the phone points to the phone itself, so it cannot
test the local portal running on the laptop. If the laptop must stay on the
company VPN, use a personal computer for the local simulator or ask IT to
approve the SMTP route and certificate trust. Check that the recipient expects
the message before retrying `--send`.
Do not set an unverified CA file or turn off certificate checking. That failed
probe did not authenticate or send a message.

## 1. What changed

```text
Same browser identity
  └─ Synthetic family
      ├─ Mother: own background, memory, consent, language, voice assignment
      └─ Father: own background, memory, consent, language, voice assignment

Select recipient + acknowledge fictional Google processing
  → validate owner / membership / revision / voice
  → reserve recipient call + select eligible memory
  → Conversation Planner (bounded plan, ≤9s; safe fallback)
  → existing Hugback Live Conversation Agent (only speaking agent)
  → Memory Reconciler (Google proposal + deterministic validation/commit)
  → release call lease
  → Quality Critic (best-effort assistant-behaviour review, ≤12s)
```

- Planner selects at most one rotating parent-authored, reviewed background reference for a possible later conversational bridge; unsuitable or sensitive candidates produce no proactive background topic. One clearly ordinary selected interest is also placed beside the plan as attributed, untrusted context so Live need not search the full excerpt list for it. Live first introduces itself as HugBack by name and responds to the caller's present-day topic. It may bring up the selected historical interest after two or three open exchanges. Live may answer direct questions from other reviewed excerpts but should ask one question at a time.
- For future synthetic calls with summary sharing enabled, a substantive call should produce a concise two- or three-sentence Signals back summary covering the main topic, another supported detail if present, and HugBack's response. A very short call may still have only one sentence. This changes only newly generated summaries; it does not recreate unavailable calls or expand the summary beyond the existing 600-character storage limit.
  guidance. It never invents free-form facts, selects identity, or grants recall.
- Live still needs a successful `claim_followup` to ask the eligible remembered
  wellbeing question. One claim per call, at most two claimed attempts per concern
  episode, cooldown, expiry, recovery and privacy rules remain authoritative.
  A claimed attempt counts even if playback is interrupted; audio generation is
  not proof of hearing. A plan does not force a question at every opening.
- Reconciler reuses the existing extractor/coordinator, not a second memory
  system. It stores validated direct self-reports for the existing five wellbeing
  topics; it is **not** a general autobiographical fact extractor.
- Critic checks named identity, unprompted AI labels, repetition, unsupported memory, topic-change handling,
  false memory-action claims, impersonation and language mismatch. It cannot
  change prompts/memory, notify children, assess parent health, or speak.
- Critic runs after memory is saved and the call lease is released. Slow/failing
  quality review does not block the next call. Generation/revision checks discard
  stale results. Privacy requests skip review; already-sent provider requests
  cannot be retracted.
- Only bounded stage states appear in the browser. Critic codes stay in a trusted
  developer report without quotes/transcripts. It is not the optional separately
  consented wellbeing signal and is **not a child recap**.
- This is orchestration/context engineering, **not model fine-tuning**.

## 2. Choose exactly one storage mode

| Setting / behaviour | SQLite | Firestore emulator | Live test Firestore |
|---|---|---|---|
| `LOCAL_DEMO_ENABLED` | `TRUE` | `TRUE` | `TRUE` |
| `HUGBACK_DEMO_STORE` | `sqlite` | `firestore` | `firestore` |
| `FIRESTORE_ENABLED` | `FALSE` | `TRUE` | `TRUE` |
| `HUGBACK_AUTH_MODE` | `development` | `development` | `firebase` |
| `HUGBACK_DEMO_PROJECT` | unused | `demo-hugback` | existing isolated test project |
| `HUGBACK_DEMO_DATABASE` | unused | `hugback-synthetic` | existing named test DB, never `(default)` |
| `FIRESTORE_EMULATOR_HOST` | unset | `127.0.0.1:8080` | unset in both shell and `.env` |
| `HUGBACK_CLOUD_TEST_ENABLED` | `FALSE` | `FALSE` | `TRUE`, only after explicit authorization |
| `HUGBACK_TEST_OWNER_UIDS` | unused | unused | comma-separated approved Firebase UIDs |
| Frontend Firebase key | unset | unset | matching Firebase project's public API key |

`LOCAL_DEMO_ENABLED` means the **synthetic simulator is enabled**, not that every
store is local. `FIRESTORE_ENABLED=TRUE` alone does not migrate data or activate
cloud context. There is **no fallback** if the selected repository fails.

In isolated Firestore mode keep these **FALSE**:
`MEMORY_ENABLED`, `FOLLOWUPS_ENABLED`, `CLOUD_INTAKE_ENABLED`,
`PORTAL_SHARING_ENABLED`. The simulator calls the canonical memory lifecycle
through its own repository; enabling the production flags is neither needed nor
permitted. Startup rejects incoherent combinations.

Enable the four roles with `HUGBACK_WORKFLOW_ENABLED=TRUE`. This adds paid
Planner/Critic requests only after the operator acknowledges fictional processing
and starts a call. Existing Live/TTS/extraction can already incur costs even with
this flag off. Offline tests do not require enabling it in your private `.env`.

### SQLite: simplest starting point

Review `.env.example` and deliberately edit only the needed keys in your existing
private `.env`. Do not overwrite your credentials with the example. Leave model
IDs at the values working for your project; example/default model strings are
not a promise of entitlement or availability.

Start backend using `./run.sh`; it now honors `HOST`/`PORT` from Settings.
Use `HOST=127.0.0.1` for these single-machine tests. Start the existing frontend
with `npm run dev`. Keep **one** origin, e.g. `http://127.0.0.1:3000`.

### Firestore emulator: storage-only local integration

`.env.firestore-emulator.example` is a **manual overlay**, not an automatically
loaded profile. An authorized operator must install/start the Firebase emulator
separately. No emulator binary or resource is provisioned by the app.

The supplied `firebase.synthetic.json` binds the emulator to loopback and names
the test database. If Firebase CLI and its compatible Java runtime are already
installed:

```sh
firebase emulators:start --only firestore \
  --project demo-hugback --config firebase.synthetic.json
```

Use this only for synthetic tests. Apply the emulator overlay and restart the
backend. Emulator storage is local, **not cloud**. Real Gemini Live/Planner/TTS
calls are **not emulated** and remain paid unless mocked.

Google documents that emulator host configuration has no `http://` prefix and
implicitly created named databases can have open rules. The supplied config
names the database and supplies deny-all browser rules; backend authorization
must still be tested independently. The emulator is not proof of production
IAM, security rules, transaction timing or quota behavior.
[Official emulator guidance](https://firebase.google.com/docs/emulator-suite/connect_firestore).

An optional actual-emulator repository test is skipped by default. With the
emulator running, apply the overlay, then:

```sh
HUGBACK_RUN_EMULATOR_TESTS=1 .venv/bin/python -m unittest discover \
  -s tests -p test_firestore_emulator.py -v
```

This creates/deletes only its own synthetic test documents using anonymous
emulator credentials. It must never target live Firestore.

### Live test Firestore: deliberate, separate activation

This code does **not** create resources, enable billing or claim live validation.
An authorized operator must first confirm:

1. An **isolated existing test project**, named Firestore database, and suitable
   backend ADC/IAM. Scope access to test resources; deny direct browser data
   access. Server Firestore uses server credentials, not a browser Firebase token.
   A Gemini API key does not authenticate Firestore. Do not commit ADC files.
2. Firebase anonymous authentication already enabled in that test project, with
   its browser API key in frontend `.env.local` as `NEXT_PUBLIC_FIREBASE_API_KEY`.
   This is not the Gemini key. Never put Google server keys in `NEXT_PUBLIC_*`.
3. Restart the frontend after public environment changes. Open `/childportal`
   using synthetic data only. Private staging can allowlist the displayed UID
   with `HUGBACK_TEST_OWNER_UIDS`. Public hackathon judge mode instead sets
   `HUGBACK_JUDGE_DEMO_ENABLED=TRUE`; the verified Firebase token automatically
   receives an isolated `firebase:UID` scope, so no token or UID must be copied.
4. Deliberately apply `.env.firestore-test.example`, filling the same project in
   `HUGBACK_DEMO_PROJECT` and `FIREBASE_PROJECT_ID`, selecting the existing named
   database, then set `HUGBACK_CLOUD_TEST_ENABLED=TRUE`. For a public synthetic
   judge deployment also set `HUGBACK_JUDGE_DEMO_ENABLED=TRUE` and include the
   deployed frontend origin in `HUGBACK_CORS_ORIGINS`.
   Remove any emulator-host setting from the shell and `.env`.
5. Restart backend, create a **new synthetic family**, and verify its mode badge
   and successful saved/reloaded state. `/health` reports configuration only;
   `demo_storage_verified=false` is intentional, not a connectivity claim.

Private staging remains loopback-only. Judge mode permits a remote peer only
when Firebase auth, Firestore, cloud-test opt-in, and an exact configured HTTPS
origin are all active. No automatic migration occurs from SQLite, the browser
preview store or the voice vault. A Firebase operator owns a separate
`firebase:UID` scope; old development voice profiles are not silently reassigned.

### Local application connected to the existing cloud test database

Firestore belongs to the Google Cloud project, not to the teammate who first
configured it. Use your own authorized Google account. These are distinct:

- `gcloud` login authenticates administrative CLI commands.
- Application Default Credentials (ADC) authenticate the Python Firestore SDK.
- The browser's Firebase ID token and server UID allowlist select the permitted
  synthetic owner. Project Owner access does not bypass application ownership.

For the existing shared setup, the selected project is
`project-84a7c715-3d60-4253-acb` and the existing named database is
`hugback-synthetic` in `us-central1`. Confirm the target before any operation;
do not create a replacement database or use real family data for tests.

An authorized operator can sign in interactively with their own account:

```sh
gcloud auth login --update-adc --project=project-84a7c715-3d60-4253-acb
```

Complete Google sign-in/consent yourself. Keep the resulting credentials outside
the repositories. Never paste tokens, ADC JSON or service-account keys into chat.
An existing `GOOGLE_APPLICATION_CREDENTIALS` environment override can take
precedence over the user ADC; inspect configuration without printing secrets.

Apply the live-test backend overlay above deliberately, with
`HUGBACK_DEMO_STORE=firestore`, matching project/Firebase settings and the approved
UID allowlist. Keep `HOST=127.0.0.1`, `PORT=8000`, email and voice enrollment off
for the storage check. There is no SQLite fallback and no implicit migration or
deletion of existing local family data. Offline tests may still use SQLite;
Firestore mode now also selects the private Firestore voice-key vault. Before
enrollment, verify deny-all browser rules on that named DB and set
`HUGBACK_FIRESTORE_VOICE_RULES_CONFIRMED=TRUE`. Existing SQLite keys are not migrated.

In the frontend's private `.env.local`, keep the matching Firebase Web API key
and set:

```dotenv
NEXT_PUBLIC_HUGBACK_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_HUGBACK_WS_URL=ws://127.0.0.1:8000/ws
NEXT_PUBLIC_HUGBACK_DEMO_MODE=true
```

Start the backend with `./run.sh` and bind the frontend explicitly to loopback:

```sh
./node_modules/.bin/next dev --hostname 127.0.0.1 --port 3000
```

Use one browser origin consistently. Localhost and the deployed website may
have different anonymous Firebase UIDs. On `/childportal`, expand **Local
connection details** at the bottom left to inspect the current UID, backend
authorization and selected adapter, including before onboarding is complete.
This panel is hidden on non-loopback hosts and never displays tokens.
Use **Retry connection** after correcting configuration/restarting the backend.
Do not clear saved browser identity or
copy another browser's tokens to recover records. Approve only the intended
local test operator UID. A 404 asking to create a synthetic family can mean
successful storage access with no family for that owner; a 403/503 is not an
empty database or permission to fall back to SQLite.

Check the displayed selected adapter and an actual authorized storage operation;
`/health` reports configuration, not successful Firestore connectivity. Any
save/reload test must use new fictional data in the named test database. This
storage setup does not authorize paid model calls, SMTP, private uploads,
deployment, or bypassing the remote simulator's loopback checks.

## 3. Where each thing lives

### Hosted demo admission — 18 October 2026

The user approved a hosted fictional-data demo without invitations or manual UID
approval. This is a separate explicit mode, not a change to the default local
simulator. See `CLOUD_RUN_CONFIGURATION_AUDIT.md` and `.env.cloud-run.example`.

Enable `HUGBACK_REMOTE_TEST_ENABLED` with one exact HTTPS
`HUGBACK_REMOTE_TEST_ORIGIN` also in `CORS_ORIGINS`, and
`HUGBACK_PUBLIC_DEMO_ENABLED` to admit new verified Firebase anonymous visitors.
No UID list is required in public-demo mode. With public admission off, the
existing UID allowlist remains required. Public admission cannot be enabled
without the remote gate, live named Firestore, matching Firebase and cloud-storage
opt-in. Development identities, emulator/SQLite, production data paths and SMTP
are not permitted in remote mode. Both standard and explicitly consented adult
child voice are supported; keys are backend-only Firestore records, not audio.

Missing/wrong Origin, invalid tokens, foreign recipient selectors and stale
revisions still fail closed. Public admission never makes one visitor's family
visible to another. The browser build must use `NEXT_PUBLIC_HUGBACK_DEMO_MODE=true`
so its calls include an explicit recipient and synthetic workflow acknowledgement.
Anyone with the link can enroll anonymously and use paid calls; the URL is not
a secret and existing per-call bounds are not a global cost cap. No new quotas
were introduced. Keep family data fictional and label post-call work as best
effort. Child voice requires explicit enrollment, verified backend-only Firestore
rules and per-recipient assignment. Private local data/keys are not migrated.

| Data | Storage in this implementation |
|---|---|
| Anonymous Firebase token/refresh token or local development UUID | Browser localStorage on that origin; not production family linking |
| Parsed full chat **preview**, if “Save local preview” selected | Browser IndexedDB, scoped to owner + recipient; not Firestore/GCS |
| Selected, explicitly reviewed fictional excerpts | Selected family repository: SQLite or isolated test Firestore |
| Recipient metadata, language, voice profile ID | Same family repository; provider key is never included |
| Bounded canonical wellbeing memory, including validated short evidence | Same repository, recipient-scoped |
| Call lifecycle/stage status | Same repository, at most 20 calls per recipient; metadata does not expose call text or summary content |
| Optional future fictional-call summary and topic notice status | Same recipient-scoped repository only after separate standing demo sharing; summary fetched through a scoped endpoint |
| Critic codes/severity/source turn + model/version | Private part of same repository, at most 20 reports; no exact evidence |
| Optional separately consented wellbeing signals | Same repository, bounded/expiring; not recaps |
| Authorized own-voice provider key | **Local**, private SQLite vault; not encrypted at rest; never browser/Firestore |
| Source voice recordings | Transient browser/backend memory; explicit Google upload only, not saved by this flow |
| Original real WhatsApp exports | **Separate** trusted Forms/Drive → internal private GCS intake, unchanged and disabled in synthetic Firestore mode |

Firestore test collections are fixed: `hugback_synthetic_test_families` and
`hugback_synthetic_test_recipients`. Family metadata and the recipient-ID list
live in the family document; each recipient document contains that recipient's
independent settings, call state, memory and bounded output. This prevents a
Mother call from rewriting Father's state. The reconstructed transactional state
is bounded to 700 KB serialized JSON before write (this is not an exact Firestore
encoded-size measurement). Older aggregate synthetic documents are read and
normalized on their next successful mutation. Recipient documents map only to
the validated owning family.

Families have seven-day **access expiry**. SQLite purges expired families on
access. In Firestore, expired families become inaccessible; this patch does
**not** provision a TTL policy or physical cleanup worker, and old recipient
index documents can remain. Operator cleanup of the isolated test database is
still needed. Do not describe access expiry as verified cloud erasure.
This expiry policy never applies to retained originals in GCS.

Browser previews expire on next access, not while the browser is closed.
Voice-key expiry/removal is local and does not revoke a provider key already
issued to Google. Original GCS files are retained until a separately authorized
erasure workflow, not deleted on import or assigned an automatic TTL.

**Therefore “Firestore enabled” does not mean “nothing local.”** Your backend,
frontend, credentials and browser identity/previews remain local. The separate
voice vault now uses the selected named Firestore database (18 October update).

## 4. Repeatable same-browser walkthrough

1. Stay at the same origin and browser profile. Do not clear identity storage
   between child setup and parent simulation. Incognito/another origin creates a
   different operator, not Mother/Father within this family.
2. `/childportal` → Family setup: create fictional Mother with simulated
   permissions and memory enabled. Add fictional Father separately; choose
   language preferences independently. Existing v1 data stays **Existing parent**.
3. Select Mother. Use `docs/examples/synthetic-agent-chat.txt` or another fictional chat, map child/parent, acknowledge the whole-chat synthetic permissions and press **Prepare Mother's background**. The browser prepares up to 24 attributed excerpts across the export: up to 20 parent messages for historical context and up to four short child replies as broad style cues. No individual selection is needed. Re-prepare an older demo background to include child style cues; merely selecting a `.txt` or saving preview does not activate context.
4. Select Father's profile and repeat with different fictional context.
   Switching recipients resets pending preview and consent. Do not put Mother’s
   preview into Father's scope.
5. Standard voice requires no enrollment. If separately authorized to use your
   own adult voice, upload sample + spoken consent with explicit Google/billing
   acknowledgement, enable it, then assign its profile **separately** to each
   intended recipient. Stale/expired/disabled profiles block calls—no fallback.
6. Use **Test a call as Mother**. Acknowledge fictional processing. State a
   fictional scenario: “I have fever today.” End the call. Wait for memory
   processing to finish; don't immediately terminate the backend.
7. Call Mother again. She should have one eligible follow-up available, not an
   unconditional scripted interrogation. Live must claim it. Continue naturally.
   A generated/claimed follow-up gets a cooldown; repeated calls are not a way
   to force the same question. Generated audio is not proof the person heard it.
8. Say “My fever is completely gone.” After successful reconciliation, it should
   no longer be selected. “A little better” must not mark complete recovery.
9. Call Father: no Mother fever memory/background should appear, even when both
   have the same child voice. End calls before changing speaker/profile.
10. Test “Don't remember this” / “Don't ask about fever.” Privacy controls must
    prevent replay/recreation; a conservative hold may require a new synthetic
    recipient for later tests. Do not clear real-user consent to make a demo pass.
11. Check bounded workflow states in the call simulator. `fallback`, `skipped`,
    `privacy_skipped` and `failed` are distinct from success. There is no
    automatic child recap. Optional fictional-call topic email requires its
    separate sharing switch and private backend SMTP configuration.

For deterministic regression testing, use the offline tests rather than waiting
24 hours or weakening cooldowns. The tests inject time and provider results.

## 5. Evals and developer inspection

From the backend repository:

```sh
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python -m evals.run --suite offline --output /tmp/hugback-offline-eval.json
```

Offline coverage includes the actual HTTP/WebSocket broker with mock Google:
two-call continuity, family isolation, single claim/cooldown, recovery, privacy,
stale writers, transaction retry/rollback, voice routing/failure, Firebase gates,
Planner schema/fallback, Critic evidence/privacy and frontend acknowledgement.
The offline eval runner overrides cloud-routing flags and Google credentials
only in its test subprocess so your chosen application `.env` is not used as a
live test destination. It never edits that file.
Frontend checks run separately in its repository:

```sh
npm test
npm run typecheck
```

The default Firestore tests use an atomic **test double**, not a real emulator or
production IAM. See the optional actual-emulator test above.

These modes contact Google and can incur charges; do **not** run without separate
authorization:

```sh
.venv/bin/python -m evals.run --suite models --allow-paid-google --output /tmp/hugback-model-eval.json
.venv/bin/python -m evals.run --suite live --allow-paid-google --output /tmp/hugback-live-eval.json
```

`models` checks the Planner, Reconciler and Critic on bundled synthetic fixtures,
including Hindi/Hinglish memory extraction. `live` runs fresh, multi-turn Live
sessions from `evals/conversation_scenarios.json` using fictional text input and
scored rules for named identity, paced background, later-call topic rotation, sparse
Mumma address, one question at a time, scope follow-ups, quiet requests,
unsupported diagnosis/email claims and a mid-call person switch.
Each rule is calibrated offline against known good and bad replies. The Critic
is an additional qualitative check; it is not the only score. Use `--repeat 3`
with paid suites when you need to see whether outcomes vary across runs.
Live discards audio and does not write a demo call, Firestore record or email.
It does **not** validate acoustic identity, TTS likeness, microphone timing,
interruption quality, production voice access or multilingual safety.
The Critic is a fallible model judge needing human calibration, not a safety
certificate. Initial datasets are deliberately small; expand with reviewed
synthetic cases, not private call exports.

The case-by-case coverage table, report interpretation and safe procedure for
adding a new eval are in `docs/AI_EVALS_BEGINNER_GUIDE.md`. A passing offline
report means the mocked regression suite and the *rubrics* passed; it does not
mean the Live model passed the conversation scenarios.

Reports contain case IDs, outcomes, counts, latency, model IDs, prompt/schema/
dataset hashes, Git commit + dirty flag. No raw transcript, keys or provider-error
body is included. Cost is reported as unmeasured, not zero. A dirty flag does not
reproduce uncommitted code; commit a reviewed change before benchmarking releases.

Trusted local operator inspection, not a public API:

```sh
.venv/bin/python scripts/inspect_demo_quality.py \
  --owner YOUR_DEVELOPMENT_ID --recipient SERVER_RECIPIENT_ID
```

For Firebase test ownership use `--owner firebase:UID`; Firestore reads require
`--allow-cloud-read`. Inspect only the authorized synthetic test database.

## 6. Environment cleanup, rollback and remaining gates

- `.env.example` is the minimal local profile; `.env.advanced.example` preserves
  legacy/internal settings as reference, not a recommended all-flags-on setup.
- Obsolete `ELARA_MODEL`, `ELARA_VOICE_NAME`, `ELARA_AUTH_MODE` have compatibility
  aliases. `scripts/migrate_env_names.py` previews renames; `--apply` atomically
  renames only these keys, keeps values, uses mode 0600, and refuses conflicts or
  symlinks. It does not print values or indiscriminately delete settings.
- Disable `HUGBACK_WORKFLOW_ENABLED` to return to the existing conversation/
  canonical-memory path. Stop active calls first. Switching repository mode is
  not migration, erasure or production promotion.
- Post-call reconciliation and Critic scheduling are **process-local**. Firestore
  persists committed state, not in-flight work. A crash can lose a pending
  extraction/review; a lease eventually expires, and “pending” may remain in
  history. Optional saved synthetic history is for display, not a retry archive;
  there is no durable outbox for email or processing retries yet.
- Live cloud IAM/SDK behavior, paid model results, real voice/acoustic quality,
  provider entitlements and phone enrollment remain separately unverified gates.
  This implementation provisions no resources, changes no billing, places no
  telephone calls, uploads no private data, and sends no notification by itself.
  The fictional SMTP path remains off until an operator privately configures it.

## Troubleshooting replacement voice and memory errors

**A created/enabled voice is not yet assigned to a recipient.** In Voice setup,
select the intended recipient in Family setup, enable the new profile, then use
**Assign this voice to [recipient]**. Only after confirmed assignment does Voice
setup show a preview link scoped to that recipient. Replacements invalidate old
profile IDs; neither enablement nor replacement changes everyone else's voice.
If no recipient is selected, the next link returns to Family setup, not `/call`.

In **Family setup**, the child enters their gender once when creating the
synthetic family, or saves it later in **Child details**. Male, female and
neutral map to the corresponding Hindi/Hinglish first-person form only for an
assigned child voice. This is not inferred from the recording, and it does not
change the parent recipient's label or memory. The standard voice keeps
feminine wording. Older custom voices can be reused after Child details are
saved; no re-enrollment or additional Google analysis is needed. English uses
the selected audio voice; spoken quality requires a separate live test.

The parent simulator's **Standard Hugback voice** label means that recipient is
configured for the preset. It now explicitly warns that your recording will not
be used. Do not create another paid replacement merely to fix a missing
assignment. Stay on the same browser origin—`localhost` and `127.0.0.1` do not
share browser identity—and never silently transfer a voice between owners.

### Retest natural conversation and voice consistency

1. Restart backend and frontend. In the child portal, select the fictional
   recipient and reopen the synthetic two-person chat in **Background**. Confirm
   the sender mapping, then press **Prepare background** again. Older prepared
   backgrounds contain parent excerpts only; the new preparation also includes
   up to four attributed child replies as broad style cues.
2. With **Standard HugBack voice**, start a fresh call. Try “Hey, hi”, “I'm
   good, what about you?”, then “I am good, what about you?” Expect a brief
   “HugBack here” opening without a role speech, no repeated how-was-your-day question, and
   one gentle familiar thread after two or three exchanges if you are open to
   conversation. Then try “No, no” or “I'd rather sit quietly”: HugBack should
   leave room rather than introduce painting or another saved detail. If you
   later say “You tell me something”, it may use one ordinary interest.
3. For an assigned child voice, save the child's stated gender in **Child details**
   before a new call. Male selects masculine first-person Hindi/Hinglish grammar;
   female selects feminine; unspecified selects neutral. This controls HugBack's
   own words, not the recipient's gender. The standard preset keeps feminine
   grammar regardless of child details.
4. Listen through several replies and language switches. The standard call
   config pins one preset voice for the entire Live session; assigned child
   voice playback uses its key and stops on TTS failure instead of falling back.
   Offline checks verify routing and grammar selection, but cannot prove that
   Google's generated timbre never varies. If it still sounds like a different
   speaker, note the approximate turn and whether **Standard** or **Child voice
   assigned** was shown in Family setup. No recording is required.
   To check interest, bring up an ordinary prepared topic and then answer its
   first question with only “yes” or “hmm.” HugBack should acknowledge it and
   change direction, without asking another question about that topic. In a new
   call, give a specific detail or ask a question back about that topic; HugBack
   may then explore that detail. Try both standard and assigned child voice,
   because they share the conversation instructions. A clear “not interested”
   or “not now” should end that topic immediately. If the next topic also draws
   only polite acknowledgements, HugBack should leave room rather than pitch
   topics indefinitely.
5. Start two fresh calls to check language. In the first, say only “Hello,
   how are you?” and expect an English greeting and English follow-up. In the
   second, start with “नमस्ते, आप कैसे हो?” and expect Hindi. Then say a full
   sentence in the other language and check that HugBack follows it without
   changing speaker voice. The saved conversation-language choice is only a
   fallback before the caller has established a language; imported chats and
   Hindi gender grammar must not force a Hindi opening. After discussing a
   painting, try a short unclear word: HugBack should clarify briefly or stay
   with painting, without inventing an unrelated food topic. This checks the
   Live model's behavior and speech recognition; offline tests verify only the
   instruction sent to it.
6. To check a mid-call language switch and a dry conversation, begin in English
   with “Hey, hi” and “All good.” Then say the full Hindi sentence “नहीं, ऐसा
   कुछ तो नहीं है।” The next reply should stay in Hindi even when its remembered
   painting fact was written in English. If you answer “टाइम नहीं मिला” and
   continue with short but open replies, HugBack should add a specific thought
   or an easy question instead of ending with “हम्म, बिल्कुल.” Once the first
   interest has naturally run dry, it may raise one different screened ordinary
   interest from this recipient's prepared chat, such as music. It should not
   list multiple interests, invent current weather, or bring up sensitive
   history. A clear request for quiet or goodbye still ends its initiative.
7. For the acknowledgement test, continue the same call with short replies:
   “Yeah, thanks”, “Okay”, “All right”, and “Yes.” These alone should not cause
   “take care”, “rest of your day”, or “goodbye.” HugBack should stay with an
   ordinary thread, introduce the one screened second interest if the first
   topic has run dry, or ask an easy present-day question. Finally say “Bye, I
   need to go”; a farewell is appropriate then. If the parent explicitly asks
   for silence, HugBack should leave space instead of trying to keep them talking.
8. For natural family-style pacing, say “I have not had time to paint,” then
   give only short acknowledgements. HugBack should not keep alternating
   painting and songs or repeat broad claims about rest, peace, and small joys.
   Say “I'm bored” and listen for one concrete, easy opening about your actual
   day. If an odd question comes up, say “What are you even asking? Ask me
   properly.” Expect a brief acknowledgement and one plain question; it should
   drop the odd topic and avoid a generic mood interview. Ask “What's the
   weather like where you are?” HugBack should not pretend to have physical
   weather or a room of its own. These are behavioral expectations for a fresh
   Live call, not guarantees from the offline prompt checks.
9. To verify that background selection is not tied to painting or songs, prepare
   a separate fictional recipient chat with ordinary parent-authored interests
   such as collecting postcards and making clay pots. Start two new calls:
   the initial bridge should rotate between those interests, and a later lull
   may bring up the other one. Child-authored lines, a health or money concern,
   and instructions embedded in the file must not become unsolicited topics.
   The browser prepares a bounded sample of the TXT, so an omitted line cannot
   become call context; check the prepared excerpt count and preview first.
10. To test speaking pace, start a fresh **Standard HugBack voice** call after
    restarting the backend. First give a short greeting, then tell a longer
    fictional story with a brief pause halfway through. HugBack should let you
    finish the thought rather than replying at that halfway pause. Next mention
    a fictional disappointment or loss and listen for a calmer, shorter reply
    with natural spacing between thoughts. Finally ask a simple upbeat question;
    it should respond normally rather than adding a dramatic delay to everything.
    The local end-of-speech setting is now 1300 ms; this gives your pauses more
    room but also adds response latency. The model controls speaking speed inside
    native audio, so judge it by listening, not by transcript text alone. If it
    still sounds rushed, note which turn and whether **Standard** or **Child
    voice assigned** was selected; do not treat offline evals as an audio test.
    Repeat the same short greeting, long story, and short-answer sequence with
    **Child voice assigned**. Its Live conversation instructions are shared with
    the standard voice, while each spoken phrase is synthesized separately with
    a short conversational-pace cue that leaves the selected child voice's
    cadence and intonation to the reference sample. Listen for a consistent
    speaker and natural sentence breaks across at least several
    turns and an English/Hindi switch. A TTS error should stop the call rather
    than switch to the standard speaker. The style cue is a request to Google,
    not proof of audible pacing or voice likeness.
11. Create a separate fictional recipient with no prepared chat. After a greeting,
    HugBack should continue from what that caller actually says and ordinary
    present-day conversation. It should not volunteer painting, songs, or any
    other specific hobby that was never supplied for that recipient.

These changes tune instructions and prepared context; they do not train model
weights or make HugBack impersonate the child.

For the separate **voice-tone continuity** test, enable that setting for the
fictional recipient in Family setup: select the recipient, tick the separate
simulated tone-consent box, and click **Enable gentle tone check-ins**. Check
that the card says **Gentle tone check-ins on**, then start a new call. Use a
headset or quiet room so speaker echo does not confuse the test. Speak three
or four substantial turns in a genuinely quieter or lower-energy tone while
still speaking clearly, for example about a slow day or feeling worn out.
HugBack may ask one tentative check-in only when the current audio gives a
clear cue; lowering microphone volume alone is insufficient. Reply “I'm fine”
and check that it accepts the answer without asking again. Try a separate
normal-voice call and a short greeting as controls: neither should produce a
mood claim. A check-in is intentionally possible rather than guaranteed; the
model must abstain when evidence is weak. This is a model-based cue, not a
measured voice baseline or a reliable health assessment.
The offline evals do not listen to audio, so this behavior needs a separately
authorized live listening test; no audio recording is required to report results.

For `memory_failed`, new calls retain a bounded `memoryErrorCode` alongside call
metadata, even if the four-role workflow is off. Categories distinguish provider
access, model/endpoint absence, quota, rejected requests, timeout/network,
invalid structured output, unavailable context/storage and interrupted processing.
Provider messages, response bodies, tokens and transcript snippets are not saved
or rendered as diagnostics. Older calls have no recoverable reason if the old
code discarded it; do not infer one from the warning alone.

A successful Live call does not prove post-call extraction succeeded. Likewise,
finding a model through Google's read-only metadata API proves neither inference
entitlement nor acceptable latency/output. Do not blame billing or silently switch
models without evidence. No automatic paid retry or transcript replay is added.
Optional workflow-status checkpoint errors no longer relabel a successful memory
commit, and intentionally disabled memory is not reported as failed just because
the optional coordinator was unavailable.

Regression checks cover replacement → enable → explicit recipient assignment →
custom-only playback with mocked Google, stale profile rejection, no cross-person
assignment, failed assignment hiding the preview, and redacted memory failures.

### Structured memory-request compatibility correction

The reported `provider_request_rejected` is a backend extraction error, not a
same-browser identity or SQLite/Firestore error. Offline inspection with the
installed `google-genai 2.28.0` found that passing our strict Pydantic models as
`response_schema` emits `additional_properties: false` inside the legacy
`responseSchema` message. That field is absent from Google's documented legacy
Schema. The original provider error body was deliberately not retained, so this
finding is consistent with the rejection, not a recovered diagnosis of that
specific response.

Memory, Planner and Critic now use `response_json_schema` through one shared
adapter. This retains `additionalProperties: false` in the JSON Schema dialect,
converts single-value `const` to `enum`, and omits defaults and string-length
keywords outside the documented generateContent JSON Schema subset. Full local
Pydantic limits (including evidence lengths, forbidden extra fields, valid topic/
subject/actions and batch bounds) remain enforced, followed by the unchanged
recipient/consent/generation/exact-evidence checks before any memory write.
[Google generateContent Schema and GenerationConfig reference](https://ai.google.dev/api/generate-content#GenerationConfig).

No model, private `.env`, voice assignment, identity, database or cloud flag
changes are required for this correction. No fallback or paid retry was added.
Tests inspect the actual SDK-serialized body for API-key and Vertex routes,
reject invalid proposals locally, and drive the broker → real extractor →
validated SQLite commit with mock Google responses. These are **offline**
contract/lifecycle checks, not live inference or entitlement verification.

After restarting/reloading the backend, refresh the existing recipient view.
Old failed calls remain failed; their discarded transcripts cannot be replayed
or recovered by this fix. For a deliberately initiated new synthetic call with
memory enabled, report a fictional current concern, end the call and wait for
processing. Check the newest call status and retained-memory count before
testing recall in another call to the **same recipient**. Keep the same origin
and browser identity. Do not clear storage, recreate a paid voice, or enable
Firestore to resolve a model-request-format error.

### Replicated voice: subtitles before audio

The Live model's draft text used to be displayed while the separate replicated
TTS request was still pending. The broker now keeps those drafts out of the
visible transcript and attaches each phrase only to its first synthesized PCM
chunk. The browser reveals the phrase from an audio-worklet render cue, not
socket arrival. Memory extraction still receives the existing transient model
transcript; no new transcript store, receipt or hearing claim is introduced.

Restart/reload both local services, refresh the page, then use a deliberately
initiated synthetic call with the existing assigned voice. Your transcript
should remain immediate; Hugback phrases should appear as their playback starts,
not the whole reply before audio. End-of-generation must not change “speaking”
to “listening” while audio remains queued. Interrupt/end before a queued phrase
and verify that its pending caption is discarded; switching recipients must
clear the old recipient's captions. No voice recreation is needed.

Offline regressions use delayed mock TTS and the actual browser-player/worklet
source with a deterministic synthetic rendering clock. They cover per-phrase
onset, multiple queued phrases, stale drain/start events, interruption, error,
end/switch, ring wrap, underflow silence and bounded-buffer overflow. This is
phrase-level UI synchronization, not provider word timestamps, reduced TTS
generation time, physical output measurement or evidence a person heard speech.

### Replicated voice: reducing application latency

The existing assigned voice key is reused, **not re-created for each reply**.
Both paths first wait for the companion-scope gate at Live turn completion.
For an allowed reply, standard voice releases the held Live audio; replicated
voice releases the held transcription through a separate Google TTS request
before playback. Live's preset audio is still discarded for replicated calls.
Google streaming TTS and a shared per-call client were already in use. Equal
latency to native Live is not promised. A blocked reply uses bounded boundary
TTS with the selected preset name or child key, never the held draft.

The 12 October optimization removes three application waits:

1. After the scope gate releases text, start the first phrase on an available clause (at least 24 characters) or
   word boundary around 96 characters instead of waiting for a sentence/280
   characters. Later phrases keep the existing batching. Short unpunctuated
   replies still wait for more text or turn completion; no token-by-token or
   timed micro-requests. Very long text retains the existing hard bound.
2. Synthesize at most one already-generated queued phrase ahead. One emitter
   preserves audio, subtitle and turn order. The current and next producer each
   have at most four queued 24,000-byte PCM chunks, in addition to provider/SDK
   event buffers. There is no speculative text, audio cache or persistent audio.
   Zero-text turn markers do not make synthesis requests.
3. Move the emitted-audio follow-up checkpoint off the audio-delivery path, with
   a one-second deadline. This is status persistence, not the post-call Memory
   Reconciler; consent/recipient checks and canonical memory rules are unchanged.

Defaults apply after a backend restart without changing a working private `.env`:

```env
HUGBACK_TTS_FIRST_PHRASE_CHARS=96
HUGBACK_TTS_LOOKAHEAD=1
```

The first-phrase setting accepts 48–280 characters; it is a segmentation target,
not a maximum duration or permission to cut a word at that size. Smaller
segments can affect phrasing and request count. Lookahead `0` disables concurrent
synthesis while keeping earlier first-phrase release and nonblocking checkpoints.
Lookahead `1` may incur extra unused synthesis if interrupted. No provider,
model, voice assignment, private environment, billing or enrollment was changed.

Interrupt/end cancels queued and active synthesis and invalidates pending
captions. Cancelling workers still occupy their slot until cleanup completes.
Producer/phrase waits have a 30-second deadline, including producer buffer
backpressure; SSE close has a two-second deadline. Errors stop custom output
without retrying in a different voice. These are cooperative async deadlines,
not guarantees against a blocked event loop or an uncooperative transport.

INFO logs now report content-free stage durations:

- `first_phrase_buffer_ms`: first **released** Live transcription to initial
  phrase enqueue; excludes the scope-gate hold.
- `queue_ms`: phrase enqueue to synthesis worker start.
- `synthesis_first_pcm_ms`: worker start to first nonempty provider PCM.
- `ordered_wait_ms`: first provider PCM to first socket send completion, including
  waiting behind previous phrases. This is **not** browser render or hearing time.

Use these in a separately authorized synthetic call to locate remaining waits.
They do not measure microphone end-of-speech, Live thinking, physical speaker
output or full mouth-to-ear latency; no real-world percentage reduction has
been measured by the offline suite.

Offline tests cover withheld synthesis through the actual WebSocket broker until
Live turn completion, shorter initial phrases after release, reset on next
turn/interruption, ordered lookahead, serial
mode, bounded buffers, slow cleanup, blocked/failed checkpoints, PCM validation,
split-chunk subtitles and fail-closed behavior. Google is mocked throughout.
Restart the backend and refresh the existing simulator; reuse the already
assigned voice—**no new recording or enrollment is needed**.

### Firestore and both voice modes: 17 October latency investigation

A small read-only probe from the local machine to the existing `us-central1`
named synthetic database measured client initialization at 4,777 ms and four
nonexistent-document reads at 2,142, 358, 1,344 and 346 ms. No family records were
read or changed by that probe. These are cold/warm SDK/network samples, **not**
measured call latency, a representative percentile, or a before/after result.

The local backend now:

- Initializes the family client off the async audio event loop.
- Batches independent recipient reads inside the same owner transaction,
  restoring membership order and retaining scope, revision and consent checks.
  Recipient-scoped operations still use dependent recipient/family reads.
  A single-recipient batch does not reduce the number of read round trips.
- Saves bounded Planner status with validated call activation, removing one
  sequential startup transaction. Neither Planner nor Live is run within a
  retryable Firestore transaction.
- Schedules standard-voice emitted-audio status persistence only after audio
  is sent, with the existing one-second deadline off the PCM path, as already
  done for replicated TTS. Held/discarded drafts are not emitted output.
  This is relevant to claimed follow-ups; unclaimed output was already a no-op.
  Status is neither speech permission nor proof someone heard the audio.

Content-free `Call stage=... elapsed_ms=...` logs separate authentication,
client initialization, family reservation, follow-up reservation, Planner,
Live connection and activation. Repository timers measure whole transactions,
including SDK retries. `Speech gate voice_mode=... hold_ms=... blocked=...`
measures first held output through its gate decision/release; it excludes the
wait before the first model output and is not microphone-to-speaker latency.
Existing TTS stage timings separate synthesis from ordered delivery.

No authorization caching, SQLite fallback, provider/model switch, speech-gate
bypass, shortened Planner timeout, VAD tuning or replication enablement is
introduced. Standard and child voice share the startup improvements; child
voice retains its additional synthesis request, bounded lookahead, and fixed
authorized key. The 18 October storage update puts keys in a separate backend-only
Firestore collection in the same named database, not in family documents.

Offline regressions use mocked Google and a transactional Firestore double:
out-of-order batches, absent/invalid recipients, activation lease checks,
blocked storage with both voice paths, and no synthesis/checkpoint of held
output. They do not establish real Firestore transaction performance or paid
voice latency. For an explicitly authorized local synthetic call, distinguish
**Start → ready** from **end of speech → audible reply**, then inspect these
stage timings. A backend restart is needed; no cloud deployment is implied.
