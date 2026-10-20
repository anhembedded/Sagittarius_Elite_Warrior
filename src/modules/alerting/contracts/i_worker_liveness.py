"""`IWorkerLiveness` — is the alert worker making progress? (`EPIC-036E1`)

The dead man's switch pings only while this says yes, so a worker that is wedged
(a lane stuck inside a channel, a thread that died) stops the ping and the
external monitor raises the alarm. Progress, not existence: a thread that is
alive but has not finished a pass for too long is not alive here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IWorkerLiveness(ABC):
    @abstractmethod
    def is_alive(self) -> bool:
        """`True` when every worker thread finished a pass recently enough.
        Safe from any thread; never raises."""

    @abstractmethod
    def stalled(self) -> tuple[str, ...]:
        """The names of the workers that have not finished a pass in time, for the
        log line that says *which* one is wedged. Empty when none is."""
