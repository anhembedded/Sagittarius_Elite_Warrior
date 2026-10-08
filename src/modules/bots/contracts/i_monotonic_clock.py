"""`EPIC-035A` — the clock an age is measured on.

`IBotClock` answers *when* (a UTC instant, stamped on a bot's record). This
answers *how long ago*: seconds on a clock that never goes backwards and that a
wall-clock step cannot move, so a price that is "60 s old" is 60 s old even when
the machine's time was set back, or the laptop slept.

@par Extension cases
  · a clock that also stops while the OS sleeps (`EPIC-035I`) — one more
    implementation of this port.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IMonotonicClock(ABC):
    """Seconds since an arbitrary start; only differences mean anything."""

    @abstractmethod
    def seconds(self) -> float:
        """Now, in seconds; never less than an earlier answer."""
