"""Small server-only Firestore adapter. No client rules are an authorization boundary."""
from copy import deepcopy

from app.config import settings


class FirestoreRepository:
    def __init__(self):
        from google.cloud import firestore
        self.firestore = firestore
        self.client = firestore.Client(project=settings.firebase_project, database=settings.FIRESTORE_DATABASE)

    def read(self, path):
        snap = self.client.document(path).get(timeout=10, retry=None)
        return snap.to_dict() if snap.exists else None

    def list(self, path, limit):
        return [snapshot.to_dict() for snapshot in self.client.collection(path).limit(limit).stream(timeout=10, retry=None)]

    def transact(self, paths, mutate):
        # All reads precede writes. The pure callback can run repeatedly on contention.
        @self.firestore.transactional
        def run(tx):
            refs = {path: self.client.document(path) for path in paths}
            state = {}
            for path, ref in refs.items():
                snapshot = ref.get(transaction=tx, timeout=10, retry=None)
                state[path] = snapshot.to_dict() if snapshot.exists else None
            writes, result = mutate(deepcopy(state))
            for path, data in writes.items():
                if path not in refs:
                    raise ValueError("Transaction cannot write an unread scope")
                tx.set(refs[path], data)
            return result
        return run(self.client.transaction(max_attempts=3))

    def close(self):
        self.client.close()
