"""Backend-only Firestore voice vault. No audio, transcripts or client writes.

Uses the already selected named database and IAM-authenticated server client.
Firestore rules must deny ALL browser reads/writes, including authenticated
owners. Only the bounded public() projection may leave this module.
"""

import copy
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from google.cloud import firestore

from app.voice.profiles import VoiceProfileStore, now
from app.voice.service import VoiceEnrollmentError, parse_voice_key


class FirestoreVoiceProfileStore:
    COLLECTION = "hugback_private_voice_profiles"
    LEASE_SECONDS = 120  # Longer than the one-shot 55s enrollment request.

    def __init__(self, client):
        self.client = client
        self.firestore = firestore

    def _transact(self, owner, operation):
        if not isinstance(owner, str) or not owner or len(owner) > 256:
            raise VoiceEnrollmentError("Invalid voice owner.")
        owner_hash = hashlib.sha256(("voice-v1:" + owner).encode()).hexdigest()
        ref = self.client.collection(self.COLLECTION).document(owner_hash)

        @self.firestore.transactional
        def run(tx):
            original = ref.get(transaction=tx).to_dict()
            state = copy.deepcopy(original) if original else {
                "schemaVersion": 1, "owner": owner_hash, "profile": None, "lease": None,
            }
            if state.get("schemaVersion") != 1 or state.get("owner") != owner_hash:
                raise VoiceEnrollmentError("Voice storage scope is invalid.")
            profile = state.get("profile")
            if profile and datetime.fromisoformat(profile["expires_at"]) <= now():
                profile["voice_key"] = None
            result = operation(state)
            # Empty tombstones fence out late enrollments after removal. No raw
            # UID or key remains. Do not rely on asynchronous TTL for validity.
            if state != original:
                state["updated_at"] = self.firestore.SERVER_TIMESTAMP
                tx.set(ref, state)
            return copy.deepcopy(result)

        return run(self.client.transaction(max_attempts=5))

    @staticmethod
    def _busy(state):
        lease = state.get("lease")
        return bool(lease and datetime.fromisoformat(lease["expires_at"]) > now())

    def status(self, owner):
        return self._transact(owner, lambda state: {
            "profile": VoiceProfileStore.public(state.get("profile")),
            "enrolling": self._busy(state),
        })

    def get(self, owner):
        return self.status(owner)["profile"]

    def begin_enrollment(self, owner):
        token = uuid.uuid4().hex

        def begin(state):
            if self._busy(state):
                raise VoiceEnrollmentError("Voice setup is already processing. Refresh its status before retrying.")
            state["lease"] = {"token": token, "expires_at": (
                now() + timedelta(seconds=self.LEASE_SECONDS)).isoformat()}
            return token

        return self._transact(owner, begin)

    def end_enrollment(self, owner, token):
        def end(state):
            if state.get("lease") and state["lease"]["token"] == token:
                state["lease"] = None
        self._transact(owner, end)

    def save(self, owner, key, provider_expiry=None, *, enrollment_token):
        if not parse_voice_key({"voiceKey": key}) or not key.startswith("voicekey_"):
            raise VoiceEnrollmentError("Google did not return a client-managed voice key.")
        created = now()
        expires = created + timedelta(days=7)
        source = "retention_limit"
        if provider_expiry is not None:
            if not isinstance(provider_expiry, datetime) or provider_expiry.tzinfo is None:
                raise VoiceEnrollmentError("Google returned an invalid voice expiry.")
            expires = min(expires, provider_expiry.astimezone(timezone.utc))
            source = "provider" if expires == provider_expiry else "retention_limit"
        if expires <= created:
            raise VoiceEnrollmentError("Google returned an already expired voice.")
        profile = {
            "profile_id": uuid.uuid4().hex, "voice_key": key,
            "created_at": created.isoformat(), "expires_at": expires.isoformat(),
            "enabled": False, "expiry_source": source,
        }

        def save(state):
            if not self._busy(state) or state["lease"]["token"] != enrollment_token:
                raise VoiceEnrollmentError("Voice setup expired or changed. Refresh voice status.")
            state["profile"] = profile
            state["lease"] = None
            return VoiceProfileStore.public(profile)
        return self._transact(owner, save)

    def select(self, owner, profile_id, enabled):
        def select(state):
            if self._busy(state):
                raise VoiceEnrollmentError("Wait for voice setup to finish.")
            profile = state.get("profile")
            if not profile or profile["profile_id"] != profile_id:
                raise VoiceEnrollmentError("Voice setup changed. Refresh the portal.")
            if enabled and not profile["voice_key"]:
                raise VoiceEnrollmentError("This voice expired. Upload fresh recordings first.")
            profile["enabled"] = bool(enabled)
            return VoiceProfileStore.public(profile)
        return self._transact(owner, select)

    def delete(self, owner):
        def delete(state):
            if self._busy(state):
                raise VoiceEnrollmentError("Wait for voice setup to finish before removing it.")
            state["profile"] = None
            state["lease"] = None
        self._transact(owner, delete)

    def resolve(self, owner, profile_id):
        def resolve(state):
            if self._busy(state):
                raise VoiceEnrollmentError("Wait for voice setup to finish.")
            profile = state.get("profile")
            if not profile or profile["profile_id"] != profile_id or not profile["enabled"]:
                raise VoiceEnrollmentError("The selected voice is no longer active. Refresh Voice setup.")
            if not profile["voice_key"]:
                raise VoiceEnrollmentError("The selected voice expired. Re-enroll or choose the standard voice.")
            return profile["voice_key"]
        return self._transact(owner, resolve)
