"""Idempotent post-call memory generation and task dispatch."""

import asyncio
import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import settings
from app.memory.models import ProcessMemoryRequest, TranscriptTurn
from app.memory.service import get_memory_service
from app.memory.store import get_session_store

logger = logging.getLogger("hugback.memory_processor")


async def process_session_memory(request: ProcessMemoryRequest) -> str:
    store = get_session_store()
    memory = get_memory_service()
    if not store.enabled:
        raise RuntimeError("Firestore must be enabled to process a persisted session")
    if not memory.enabled:
        await store.update_status(request.user_id, request.session_id, "skipped")
        return "skipped"

    session = await store.get_session(request.user_id, request.session_id)
    if session is None:
        raise LookupError("Session does not exist")
    if session.get("memory_status") == "processed":
        return "already_processed"
    if session.get("memory_status") == "processing":
        updated_at = session.get("memory_updated_at")
        if (
            isinstance(updated_at, datetime)
            and datetime.now(timezone.utc) - updated_at < timedelta(minutes=10)
        ):
            # Returning an error makes Cloud Tasks retry. The active worker will
            # normally finish first, after which the retry becomes a no-op.
            raise RuntimeError("Memory processing is already in progress")
    if not session.get("user_turn_count"):
        await store.update_status(request.user_id, request.session_id, "skipped")
        return "skipped"

    turns = [TranscriptTurn.model_validate(item) for item in session.get("transcript", [])]
    await store.update_status(request.user_id, request.session_id, "processing")
    try:
        await memory.generate(request.user_id, turns)
    except Exception as exc:
        await store.update_status(
            request.user_id, request.session_id, "failed", str(exc)
        )
        raise
    await store.update_status(request.user_id, request.session_id, "processed")
    return "processed"


async def dispatch_memory_processing(request: ProcessMemoryRequest) -> None:
    if not get_memory_service().enabled:
        return
    if settings.MEMORY_PROCESSING_MODE.lower() == "cloud_tasks":
        await asyncio.to_thread(_enqueue_cloud_task, request)
        return
    await process_session_memory(request)


def _enqueue_cloud_task(request: ProcessMemoryRequest) -> None:
    if not settings.MEMORY_PROCESSOR_URL:
        raise RuntimeError("MEMORY_PROCESSOR_URL is required for Cloud Tasks mode")
    try:
        from google.cloud import tasks_v2
    except ImportError as exc:
        raise RuntimeError("google-cloud-tasks is required for Cloud Tasks mode") from exc

    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(
        settings.GOOGLE_CLOUD_PROJECT,
        settings.CLOUD_TASKS_LOCATION,
        settings.CLOUD_TASKS_QUEUE,
    )
    headers = {"Content-Type": "application/json"}
    if settings.MEMORY_TASK_SECRET:
        headers["X-Hugback-Task-Secret"] = settings.MEMORY_TASK_SECRET
    http_request: dict[str, Any] = {
        "http_method": tasks_v2.HttpMethod.POST,
        "url": settings.MEMORY_PROCESSOR_URL,
        "headers": headers,
        "body": request.model_dump_json().encode("utf-8"),
    }
    if settings.CLOUD_TASKS_SERVICE_ACCOUNT:
        http_request["oidc_token"] = {
            "service_account_email": settings.CLOUD_TASKS_SERVICE_ACCOUNT,
            "audience": settings.MEMORY_PROCESSOR_URL,
        }
    client.create_task(parent=parent, task={"http_request": http_request})


def task_request_is_authorized(headers: Any) -> bool:
    """Cloud Run IAM is primary; this secret supports local/private deployments."""
    if settings.MEMORY_TASK_SECRET:
        supplied = headers.get("x-hugback-task-secret", "")
        return hmac.compare_digest(supplied, settings.MEMORY_TASK_SECRET)

    if not settings.CLOUD_TASKS_SERVICE_ACCOUNT or not settings.MEMORY_PROCESSOR_URL:
        return False
    authorization = headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        return False
    try:
        from google.auth.transport.requests import Request as GoogleAuthRequest
        from google.oauth2 import id_token

        claims = id_token.verify_oauth2_token(
            authorization.removeprefix("Bearer "),
            GoogleAuthRequest(),
            audience=settings.MEMORY_PROCESSOR_URL,
        )
    except Exception as exc:
        logger.warning("Cloud Tasks OIDC verification failed: %s", exc)
        return False
    return bool(
        claims.get("email_verified")
        and claims.get("email") == settings.CLOUD_TASKS_SERVICE_ACCOUNT
    )
