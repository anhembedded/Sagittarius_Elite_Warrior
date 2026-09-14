from __future__ import annotations

import threading
import time
from collections.abc import Callable


class ThreadSafeRateLimiter:
    """
    @brief Thread-safe rate limiter (Throttler Pattern) for synchronizing dispatch rates.
    @details Ensures that consecutive calls across multiple concurrent threads maintain
    a minimum time interval (`delay_sec`) between executions.
    """

    _CANCELLATION_POLL_INTERVAL_SEC: float = 0.05

    def __init__(self, delay_sec: float = 0.0) -> None:
        self._delay_sec = max(0.0, float(delay_sec))
        self._last_time = 0.0
        self._lock = threading.Lock()

    @property
    def delay_sec(self) -> float:
        return self._delay_sec

    @delay_sec.setter
    def delay_sec(self, value: float) -> None:
        self._delay_sec = max(0.0, float(value))

    def acquire(
        self,
        cancellation_requested: Callable[[], bool] | None = None,
    ) -> None:
        """Blocks until the required interval since the last dispatch has elapsed."""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_time
            if elapsed < self._delay_sec:
                remaining = self._delay_sec - elapsed
                if cancellation_requested is None:
                    time.sleep(remaining)
                else:
                    while remaining > 0:
                        if cancellation_requested():
                            return
                        sleep_chunk = min(
                            self._CANCELLATION_POLL_INTERVAL_SEC, remaining
                        )
                        time.sleep(sleep_chunk)
                        remaining -= sleep_chunk
            self._last_time = time.time()

    def reset(self) -> None:
        """Resets the rate limiter timer."""
        with self._lock:
            self._last_time = 0.0
