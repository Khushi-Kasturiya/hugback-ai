"""Public, content-free description of Hugback's runtime architecture.

This module deliberately reports capabilities and boundaries, not credentials,
project identifiers, private records, or claims that configured cloud services
have passed a live probe.
"""

from app.config import settings


def architecture_manifest() -> dict:
    """Return the canonical deployed design and the selected runtime adapters."""
    firestore_selected = settings.HUGBACK_DEMO_STORE == "firestore"
    return {
        "version": "google-cloud-v1",
        "principle": (
            "Models propose bounded actions; authenticated, recipient-scoped "
            "policy code authorizes every durable effect."
        ),
        "canonicalDeployment": {
            "identity": "Firebase Authentication",
            "realtimeCompute": "Cloud Run WebSocket broker",
            "conversation": "Gemini Live",
            "operationalState": "Cloud Firestore",
            "retainedOriginals": "Google Cloud Storage",
            "durableBackgroundWork": "Cloud Tasks",
            "observability": "Google Cloud Logging and Trace",
        },
        "runtime": {
            "identity": "firebase" if settings.HUGBACK_AUTH_MODE == "firebase" else "loopback_development",
            "familyState": "firestore" if firestore_selected else "sqlite_test_adapter",
            "browserDrafts": "indexeddb_private_preconsent_staging",
            "voiceSecrets": "firestore_backend_only" if firestore_selected else "sqlite_test_adapter",
            "postCallExecution": (
                "cloud_tasks" if settings.MEMORY_PROCESSING_MODE == "cloud_tasks"
                else "inline_best_effort"
            ),
        },
        "stages": [
            {
                "name": "planner",
                "when": "before_call",
                "authority": "advisory",
                "output": "one bounded conversation plan",
            },
            {
                "name": "live",
                "when": "during_call",
                "authority": "speaking_agent",
                "output": "bidirectional audio and bounded tool proposals",
            },
            {
                "name": "reconciler",
                "when": "after_call",
                "authority": "proposal_only",
                "output": "evidence-linked wellbeing observations",
            },
            {
                "name": "critic",
                "when": "after_commit",
                "authority": "advisory",
                "output": "content-free quality findings",
            },
        ],
        "trustControls": [
            "authenticated Firebase identity",
            "recipient membership validation",
            "optimistic recipient revision",
            "consent generation recheck",
            "strict structured outputs",
            "exact source-evidence validation",
            "transactional commit",
            "stale result rejection",
        ],
        "storageBoundaries": [
            {
                "data": "canonical family, recipient, call and consent state",
                "store": "firestore",
                "reason": "server-authorized transactional source of truth",
            },
            {
                "data": "unapproved full chat preview and local profile photo",
                "store": "indexeddb",
                "reason": "private browser staging; never uploaded merely by selecting a file",
            },
            {
                "data": "temporary replicated voice provider key",
                "store": "firestore" if settings.HUGBACK_DEMO_STORE == "firestore" else "sqlite_test_adapter",
                "reason": "backend-only owner-scoped vault; never exposed to browsers; no recordings",
            },
            {
                "data": "retained original intake files",
                "store": "cloud_storage",
                "reason": "private object storage rather than Firestore documents",
            },
        ],
        "configured": {
            "firestore": settings.FIRESTORE_ENABLED,
            "firebaseAuth": settings.HUGBACK_AUTH_MODE == "firebase",
            "fourStageWorkflow": settings.HUGBACK_WORKFLOW_ENABLED,
            "structuredContextExtraction": settings.HUGBACK_CONTEXT_EXTRACTION_ENABLED,
            "judgeDemo": settings.HUGBACK_JUDGE_DEMO_ENABLED,
            "replicatedTts": settings.HUGBACK_REPLICATED_TTS_ENABLED,
            "firestoreVoiceRulesConfirmed": settings.HUGBACK_FIRESTORE_VOICE_RULES_CONFIRMED,
            "cloudIntake": settings.CLOUD_INTAKE_ENABLED,
            "remoteSyntheticTest": settings.HUGBACK_REMOTE_TEST_ENABLED,
            "publicDemo": settings.HUGBACK_PUBLIC_DEMO_ENABLED,
        },
        "notes": [
            "SQLite is not part of the canonical deployed family-state architecture.",
            "IndexedDB is a privacy boundary for pre-consent drafts, not canonical state.",
            "Configured means selected by settings; it is not a successful cloud probe.",
        ],
    }
