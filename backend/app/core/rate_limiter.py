"""Thread-safe sliding-window rate limiter for API protection."""

import threading
import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    """In-memory sliding-window rate limiter with per-bucket limits.

    Designed with a simple `check(key, limit, window_seconds)` contract so it
    can be swapped cleanly for a Redis-backed implementation in multi-replica deployments.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(
        self, key: str, limit: int, window_seconds: int = 60
    ) -> tuple[bool, int, int]:
        """Return (allowed, remaining, retry_after_seconds)."""
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, int(window_seconds - (now - bucket[0])) + 1)
                return False, 0, retry_after
            bucket.append(now)
            remaining = max(0, limit - len(bucket))
            return True, remaining, 0

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


rate_limiter = SlidingWindowRateLimiter()
