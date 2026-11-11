"""In-memory limiter for failed login attempts.

State lives in the process, which is fine for a single uvicorn worker (the Docker
setup). Only *failed* attempts count, so normal use is never affected.
"""
import threading
import time
from collections import deque
from typing import Callable


class FailureLimiter:
    def __init__(self, max_failures: int, window_seconds: float, clock: Callable[[], float] = time.monotonic):
        self.max_failures = max_failures
        self.window = window_seconds
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> deque[float]:
        hits = self._failures.get(key)
        if hits is None:
            return deque()
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if not hits:
            del self._failures[key]
            return deque()
        return hits

    def retry_after(self, key: str) -> int:
        """Seconds until another attempt is allowed; 0 if the key is not blocked."""
        with self._lock:
            now = self._clock()
            hits = self._recent(key, now)
            if len(hits) < self.max_failures:
                return 0
            return max(1, int(hits[0] + self.window - now) + 1)

    def record_failure(self, key: str) -> None:
        with self._lock:
            now = self._clock()
            self._recent(key, now)
            self._failures.setdefault(key, deque()).append(now)
            if len(self._failures) > 10_000:  # bound memory under a flood of distinct keys
                for k in list(self._failures):
                    self._recent(k, now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()


WINDOW_SECONDS = 15 * 60
# Per client IP and household name: stops guessing one household's password
login_by_name = FailureLimiter(max_failures=5, window_seconds=WINDOW_SECONDS)
# Per client IP across all names: stops trying many households from one address
login_by_ip = FailureLimiter(max_failures=20, window_seconds=WINDOW_SECONDS)
