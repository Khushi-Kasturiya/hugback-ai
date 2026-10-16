"""Firestore transaction adapter for a bounded, parent-scoped memory document."""

from typing import Callable, Protocol, TypeVar

from app.memory.followups import FollowupState

T = TypeVar("T")


class FollowupStore(Protocol):
    async def transact(self, owner: str, mutate: Callable[[FollowupState], T]) -> T: ...


class FirestoreFollowupStore:
    def __init__(self, project: str, database: str):
        from google.cloud import firestore
        self._firestore = firestore
        self._client = firestore.AsyncClient(project=project, database=database)

    async def transact(self, owner: str, mutate: Callable[[FollowupState], T]) -> T:
        # Owner comes only from authenticated server identity, never a tool arg.
        if not owner or "/" in owner:
            raise ValueError("Invalid owner scope")
        ref = self._client.collection("users").document(owner).collection("private_memory").document("followups")

        @self._firestore.async_transactional
        async def update(transaction):
            snapshot = await ref.get(transaction=transaction)
            state = FollowupState.model_validate(snapshot.to_dict() or {})
            before = state.model_dump(mode="python")
            result = mutate(state)
            after = state.model_dump(mode="python")
            if after != before:
                transaction.set(ref, after)
            return result

        return await update(self._client.transaction())
