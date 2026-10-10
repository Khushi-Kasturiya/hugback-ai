# Elara backend

FastAPI broker for Gemini Live audio with authenticated, user-scoped long-term
memory.

## Local development

1. Copy `.env.example` to `.env` and configure Gemini authentication.
2. Leave `ELARA_AUTH_MODE=development`, `MEMORY_ENABLED=FALSE`, and
   `FIRESTORE_ENABLED=FALSE` for a memory-free local call.
3. Install dependencies and run the service:

   ```bash
   pip install -e .
   ./run.sh
   ```

The frontend stores a random development user ID in the browser. Development
IDs provide continuity, not security, and must not be enabled in production.

## Enable durable memory

1. Enable the Agent Platform, Firestore, Cloud Tasks, and Firebase Authentication
   APIs in the Google Cloud project.
2. Enable Anonymous Authentication in Firebase Console.
3. Authenticate locally with Application Default Credentials.
4. Create the configured Memory Bank once:

   ```bash
   python scripts/create_memory_bank.py
   ```

5. Copy its printed resource name into `MEMORY_BANK_NAME`, then set:

   ```dotenv
   MEMORY_ENABLED=TRUE
   FIRESTORE_ENABLED=TRUE
   ELARA_AUTH_MODE=firebase
   FIREBASE_PROJECT_ID=your-project-id
   ```

6. Set `NEXT_PUBLIC_FIREBASE_API_KEY` in the frontend `.env.local` file.

The Memory Bank setup uses `gemini-embedding-001` for multilingual semantic
retrieval, a structured `elara-care-profile`, memory revisions, and TTL refresh
when a fact is reinforced.

## Production post-call processing

Create a Cloud Tasks queue and configure the deployed backend:

```dotenv
MEMORY_PROCESSING_MODE=cloud_tasks
CLOUD_TASKS_LOCATION=us-central1
CLOUD_TASKS_QUEUE=elara-memory
MEMORY_PROCESSOR_URL=https://YOUR_SERVICE/internal/memory/process
CLOUD_TASKS_SERVICE_ACCOUNT=YOUR_TASK_INVOKER_SERVICE_ACCOUNT
```

The task service account's OIDC identity is verified by the endpoint. For local
task testing, use `MEMORY_TASK_SECRET` instead. Never deploy with development
authentication.

## Privacy controls

- `GET /api/memories` returns the authenticated user's structured profiles and
  natural-language facts.
- `DELETE /api/memories` purges that user's Memory Bank scope and Firestore
  transcripts.

With Firebase authentication, send `Authorization: Bearer FIREBASE_ID_TOKEN`.
For local development only, send `X-Elara-Development-User: BROWSER_USER_ID`.

## Tests

```bash
python -m unittest discover -s tests -v
```
