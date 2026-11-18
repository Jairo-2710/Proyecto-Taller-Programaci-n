"""In-memory rate limiter for login attempts."""

import threading
import time


class LoginRateLimiter:
    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 60,
        lockout_seconds: int = 300,
    ):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._attempts = {}
        self._blocked_until = {}
        self._lock = threading.Lock()

    def check(self, key: tuple) -> int:
        """Return remaining lockout seconds, or zero if allowed."""
        now = time.monotonic()

        with self._lock:
            blocked_until = self._blocked_until.get(key, 0)

            if blocked_until > now:
                return max(1, int(blocked_until - now + 0.999))

            if blocked_until:
                self._blocked_until.pop(key, None)
                self._attempts.pop(key, None)

            attempts = self._attempts.get(key, [])
            attempts = [
                timestamp
                for timestamp in attempts
                if now - timestamp < self.window_seconds
            ]
            self._attempts[key] = attempts

            return 0

    def record_failure(self, key: tuple) -> None:
        """Register a failed login attempt."""
        now = time.monotonic()

        with self._lock:
            attempts = self._attempts.get(key, [])
            attempts = [
                timestamp
                for timestamp in attempts
                if now - timestamp < self.window_seconds
            ]

            attempts.append(now)
            self._attempts[key] = attempts

            if len(attempts) >= self.max_attempts:
                self._blocked_until[key] = now + self.lockout_seconds
                self._attempts.pop(key, None)

    def reset(self, key: tuple) -> None:
        """Clear attempts after a successful login."""
        with self._lock:
            self._attempts.pop(key, None)
            self._blocked_until.pop(key, None)

    def clear(self) -> None:
        """Clear all limiter state, useful for isolated tests."""
        with self._lock:
            self._attempts.clear()
            self._blocked_until.clear()


login_limiter = LoginRateLimiter()
