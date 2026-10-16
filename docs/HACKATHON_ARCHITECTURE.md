# HugBack canonical Google Cloud architecture

This is the architecture to present, deploy and evaluate. Compatibility and
offline-test adapters are deliberately omitted from the main diagram.

```text
Next.js child setup + parent call
        │ Firebase ID token / PCM WebSocket
        ▼
Cloud Run — authenticated FastAPI media and policy broker
        │
        ├── Planner ───────────── bounded pre-call proposal
        ├── Gemini Live ───────── only speaking agent
        ├── Memory Reconciler ─── evidence-linked post-call proposal
        └── Quality Critic ────── content-free behaviour findings
        │
        ▼
Policy commit firewall
  identity → membership → revision → consent generation
  → schema → exact evidence → transaction
        │
        ├── Cloud Firestore ───── canonical operational state
        ├── Cloud Storage ─────── retained original intake files
        └── Cloud Tasks ───────── durable production post-call work
```

The architectural claim is not that every model call is autonomous. HugBack is
a deterministic four-stage agentic workflow with one real-time speaking agent
and three bounded specialists. Models never choose an owner, recipient, consent
grant, provider voice key or durable write target.

## One canonical state store

Cloud Firestore is the canonical deployed source of truth for family,
recipient, call, consent and bounded memory state. The isolated SQLite family
repository remains only as a fast offline test adapter. It is not a second
deployed database and must not be shown in the primary judging diagram.

Firestore keeps family metadata separate from recipient documents. Each
recipient document owns its settings, call state, consent generations, bounded
memory and outputs. A Mother call therefore does not rewrite Father's state or
create a single hot, ever-growing family aggregate.

The Firestore emulator is also a test adapter. Live test mode uses an isolated,
named Firestore database and verified Firebase identities. Neither mode silently
falls back to another repository.

## Why IndexedDB remains

IndexedDB is not canonical state. It is a browser-private staging boundary for:

- a full parsed chat preview before the user approves bounded excerpts; and
- a local prototype profile photo.

Selecting a private chat file must not upload the full conversation. Only the
explicitly authorized, bounded excerpts cross the browser/backend boundary.
This is a privacy property, not an architectural accident.

If cross-device photos become a product requirement, move the photo to a private
Cloud Storage object with an authenticated backend upload flow. Do not put image
bytes in Firestore. The chat preview should remain local unless a separately
designed, consented retained-original intake flow is used.

## Why a local SQLite voice vault remains

The voice SQLite file is not family state. It is a temporary, server-only vault
for a Google-issued replicated-voice key in the single-machine prototype. The
key must never enter browser storage or the synthetic Firestore family record.

For a real deployment, replace this adapter with Secret Manager or a purpose-
built encrypted secret store whose IAM scope matches the enrolled owner. Do not
store provider voice secrets in ordinary Firestore documents.

## Judge-visible proof

The frontend `/architecture` route reads the content-free
`GET /api/architecture` manifest and shows:

- the canonical Google services;
- the four workflow stages and their authority;
- the deterministic commit firewall;
- exact storage responsibilities; and
- the adapter currently selected by the running backend.

The endpoint reports configuration, not successful cloud connectivity, and
never returns tokens, project identifiers, private records or provider keys.

## Deployment target versus current prototype

| Concern | Canonical deployment | Local/offline adapter |
|---|---|---|
| Identity | Firebase Authentication | loopback development UUID |
| Family state | Cloud Firestore | SQLite test repository |
| Live compute | Cloud Run | local Uvicorn |
| Conversation | Gemini Live | mocked provider in tests |
| Pre-consent chat preview | browser IndexedDB | same |
| Original retained file | private Cloud Storage | offline validation fixture |
| Voice provider key | managed secret store target | local mode-0600 SQLite vault |
| Post-call work | Cloud Tasks target | bounded inline test execution |

The production target in this table is an architectural direction. Resource
creation, IAM validation, verified participant enrollment, telephone calling,
and migration of current local voice profiles remain separate release gates.
