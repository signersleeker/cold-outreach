"""Single-password app login.

One user, one password from the environment. Compared with compare_digest so a
wrong guess costs the same time as a right one, and rate-limited so the password
cannot be brute-forced from localhost by something else on the machine.
"""

from __future__ import annotations

import hmac
import threading
from dataclasses import dataclass, field
from time import monotonic

MAX_ATTEMPTS = 8
WINDOW_SECONDS = 300.0


def password_matches(supplied: str, configured: str) -> bool:
    if not configured:
        return False
    return hmac.compare_digest(supplied.encode("utf-8"), configured.encode("utf-8"))


@dataclass
class LoginThrottle:
    """In-process failed-attempt counter. Single user, single process."""

    max_attempts: int = MAX_ATTEMPTS
    window_seconds: float = WINDOW_SECONDS
    _attempts: dict[str, list[float]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _prune(self, key: str, now: float) -> list[float]:
        recent = [t for t in self._attempts.get(key, []) if now - t < self.window_seconds]
        self._attempts[key] = recent
        return recent

    def is_locked(self, key: str) -> bool:
        with self._lock:
            return len(self._prune(key, monotonic())) >= self.max_attempts

    def record_failure(self, key: str) -> None:
        with self._lock:
            now = monotonic()
            self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def retry_after_seconds(self, key: str) -> int:
        with self._lock:
            recent = self._prune(key, monotonic())
            if not recent:
                return 0
            return max(1, int(self.window_seconds - (monotonic() - recent[0])))
