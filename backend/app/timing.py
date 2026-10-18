"""Content-free application timings, not microphone-to-speaker measurements."""
import logging
import time
from contextlib import contextmanager

logger = logging.getLogger("hugback.timing")


@contextmanager
def stage_timer(stage):
    """Call with a fixed code-owned stage name, never user/provider content."""
    started = time.monotonic()
    succeeded = False
    try:
        yield
        succeeded = True
    finally:
        logger.info("Call stage=%s elapsed_ms=%d succeeded=%s",
                    stage, round((time.monotonic() - started) * 1000), succeeded)
