"""Memory Reconciler role: existing evidence-bounded Google proposal extractor.

FollowupCoordinator/apply_observations remain the only memory commit authority.
No alternative store, transcript archive, or second memory implementation.
"""
from app.memory.followup_extractor import GoogleFollowupExtractor

class MemoryReconciler(GoogleFollowupExtractor):
    prompt_version = "reconciler-v1"
