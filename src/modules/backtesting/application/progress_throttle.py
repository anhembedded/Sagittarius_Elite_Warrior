from __future__ import annotations

from collections.abc import Callable
from time import perf_counter

#: BUG-033 — a run processing millions of ticks (Realtime/tick-level) or a
#: very large candle count (Static) can cross an index-based throttle
#: (`index % N == 0`) tens of thousands of times over a single run. Each
#: crossing fires `progress_callback`, which the presentation layer turns
#: into a cross-thread Qt signal → Property write → QML notify → an
#: `AppProgressBar` animation retrigger. At ~10,000+ crossings in a burst,
#: draining that queue can occupy the Qt main thread continuously long
#: enough to trip the UI freeze watchdog (observed: 5.2s, 2.59M ticks,
#: 256-tick throttle). Gating by wall-clock time instead bounds the
#: absolute emission rate no matter how many iterations a run has.
_DEFAULT_MIN_INTERVAL_SECONDS = 0.15


class ProgressThrottle:
    """Decides whether a long-running loop's `index`-th iteration should
    fire its progress callback — always yes for the first and last index
    (so a progress bar never looks stuck at 0% or fails to reach 100%),
    otherwise only once at least `min_interval_seconds` of real time has
    elapsed since the last time it said yes.

    `clock` is injectable so tests can control elapsed time deterministically
    instead of relying on `time.sleep()`."""

    def __init__(
        self,
        min_interval_seconds: float = _DEFAULT_MIN_INTERVAL_SECONDS,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        self._min_interval_seconds = min_interval_seconds
        self._clock = clock
        self._last_emit_time: float | None = None

    def should_emit(self, index: int, total: int) -> bool:
        if index <= 1 or index >= total:
            self._last_emit_time = self._clock()
            return True
        now = self._clock()
        if (
            self._last_emit_time is None
            or (now - self._last_emit_time) >= self._min_interval_seconds
        ):
            self._last_emit_time = now
            return True
        return False
