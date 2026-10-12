"""Content-free error categories. Never persist provider messages or transcripts."""

import asyncio

import httpx
from google.genai import errors
from pydantic import ValidationError

MEMORY_ERROR_CODES = frozenset({
    "provider_access", "model_unavailable", "rate_limited", "provider_unavailable",
    "provider_request_rejected", "timeout", "network_unavailable", "invalid_output",
    "context_unavailable", "storage_unavailable", "processing_interrupted", "processing_failed",
})


def memory_error_code(error: Exception) -> str:
    if isinstance(error, (asyncio.TimeoutError, httpx.TimeoutException)):
        return "timeout"
    if isinstance(error, httpx.TransportError):
        return "network_unavailable"
    if isinstance(error, ValidationError):
        return "invalid_output"
    if isinstance(error, errors.APIError):
        if error.code in (401, 403):
            return "provider_access"
        if error.code == 404:
            return "model_unavailable"
        if error.code == 429:
            return "rate_limited"
        if isinstance(error.code, int) and error.code >= 500:
            return "provider_unavailable"
        return "provider_request_rejected"
    return "processing_failed"
