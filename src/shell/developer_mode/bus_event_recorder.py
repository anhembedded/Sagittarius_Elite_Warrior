"""What the Developer mode's event log is fed from (`EPIC-033P`).

@details An Engine `IBusObserver` (`bus_observers.py`), registered with
`add_bus_observer`: the Engine calls it once per emit with the event's name
and how many handlers heard it, and once per handler that raised. It runs
inside the dispatch path, on whichever thread emits, so it only appends a
`BusEventRecord` to a bounded buffer; the UI thread takes them with `drain()`
on a timer. One update per event would push every tick through the UI thread,
the `BUG-042` freeze (`logging-rule.md` §6).

The buffer keeps the newest `capacity` records. What a burst between two
drains pushes out is counted in `lost`, never dropped silently.

Qt-free on purpose: the observer half is tested against the Engine's real bus
without a `QApplication`.
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sagittarius_engine.infrastructure.event_bus.bus_observers import (
    IBusObserver,
    add_bus_observer,
    remove_bus_observer,
)

#: Records kept between two drains. Drained every 250 ms, it overflows only
#: while the bus publishes over 4 000 events a second; the log keeps its own,
#: larger window.
DEFAULT_CAPACITY = 1000


@dataclass(frozen=True, slots=True)
class BusEventRecord:
    """One emit, or one handler that raised while handling it."""

    at: datetime
    event: str
    #: How many handlers heard it; `None` on a failure record.
    handlers: int | None
    #: `"<handler>: <exception type>: <message>"` when a handler raised.
    failure: str | None = None

    @property
    def outcome(self) -> str:
        if self.failure is not None:
            return f"failed in {self.failure}"
        if not self.handlers:
            return "no handler"
        noun = "handler" if self.handlers == 1 else "handlers"
        return f"delivered to {self.handlers} {noun}"


def _now() -> datetime:
    return datetime.now(UTC)


class BusEventRecorder(IBusObserver):
    """@brief Records what the bus does, for the UI thread to drain."""

    def __init__(
        self,
        capacity: int = DEFAULT_CAPACITY,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._records: deque[BusEventRecord] = deque(maxlen=capacity)
        self._clock = clock
        self._lock = threading.Lock()
        self._lost = 0

    @property
    def lost(self) -> int:
        """How many records a full buffer pushed out before a drain took them."""
        return self._lost

    def start(self) -> None:
        add_bus_observer(self)

    def stop(self) -> None:
        remove_bus_observer(self)

    def event_emitted(self, event_name: str, handler_count: int) -> None:
        self._append(BusEventRecord(self._clock(), event_name, handler_count))

    def handler_failed(self, event_name: str, handler: str, exc: BaseException) -> None:
        failure = f"{handler}: {type(exc).__name__}: {exc}"
        self._append(BusEventRecord(self._clock(), event_name, None, failure))

    def drain(self) -> tuple[BusEventRecord, ...]:
        """Every record since the last drain, oldest first."""
        with self._lock:
            records = tuple(self._records)
            self._records.clear()
        return records

    def _append(self, record: BusEventRecord) -> None:
        with self._lock:
            if len(self._records) == self._records.maxlen:
                self._lost += 1
            self._records.append(record)
