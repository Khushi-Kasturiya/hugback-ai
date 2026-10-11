"""WebSocket caller authentication and user-scope derivation."""

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from app.config import settings

logger = logging.getLogger("hugback.auth")

_DEVELOPMENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$")
_FIREBASE_CLOCK_SKEW_SECONDS = 30


class AuthenticationError(ValueError):
    """Raised when the WebSocket authentication envelope is invalid."""


@dataclass(frozen=True)
class UserIdentity:
    user_id: str
    provider: str


def _verify_firebase_id_token(token: str) -> dict[str, Any]:
    """Verify a Firebase ID token with Google's public signing certificates."""
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token

    project_id = settings.firebase_project
    decoded = id_token.verify_firebase_token(
        token,
        Request(),
        audience=project_id,
        clock_skew_in_seconds=_FIREBASE_CLOCK_SKEW_SECONDS,
    )

    if decoded.get("iss") != f"https://securetoken.google.com/{project_id}":
        raise ValueError("Firebase token issuer did not match the configured project")

    subject = decoded.get("sub")
    if not isinstance(subject, str) or not 1 <= len(subject) <= 128:
        raise ValueError("Firebase token subject is invalid")

    auth_time = decoded.get("auth_time")
    if not isinstance(auth_time, (int, float)):
        raise ValueError("Firebase token auth_time is missing")
    if auth_time > time.time() + _FIREBASE_CLOCK_SKEW_SECONDS:
        raise ValueError("Firebase token auth_time is in the future")

    return decoded


async def authenticate_message(message: dict[str, Any]) -> UserIdentity:
    """Authenticate the first WebSocket message and return a trusted user ID."""
    if message.get("type") != "authenticate":
        raise AuthenticationError("The first message must authenticate the caller")

    if settings.HUGBACK_AUTH_MODE.lower() == "firebase":
        token = message.get("idToken")
        if not isinstance(token, str) or not token:
            raise AuthenticationError("A Firebase ID token is required")

        try:
            decoded = await asyncio.to_thread(_verify_firebase_id_token, token)
        except Exception as exc:
            logger.warning("Firebase token verification failed: %s", exc)
            raise AuthenticationError("Invalid or expired Firebase ID token") from exc

        uid = decoded.get("uid") or decoded.get("sub")
        if not isinstance(uid, str) or not uid:
            raise AuthenticationError("Firebase token did not contain a user ID")
        return UserIdentity(user_id=uid, provider="firebase")

    if settings.HUGBACK_AUTH_MODE.lower() != "development":
        raise AuthenticationError("Unsupported authentication mode")
    user_id = message.get("userId")
    if not isinstance(user_id, str) or not _DEVELOPMENT_ID.fullmatch(user_id):
        raise AuthenticationError("A valid development user ID is required")
    return UserIdentity(user_id=user_id, provider="development")


async def authenticate_http_headers(headers: Any) -> UserIdentity:
    """Authenticate a privacy-control HTTP request using the configured mode."""
    if settings.HUGBACK_AUTH_MODE.lower() == "firebase":
        authorization = headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            raise AuthenticationError("A Firebase bearer token is required")
        return await authenticate_message(
            {
                "type": "authenticate",
                "idToken": authorization.removeprefix("Bearer "),
            }
        )
    return await authenticate_message(
        {
            "type": "authenticate",
            "userId": headers.get("x-hugback-development-user"),
        }
    )
