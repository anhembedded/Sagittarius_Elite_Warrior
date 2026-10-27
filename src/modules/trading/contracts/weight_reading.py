"""`EPIC-047H` — a venue's request weight as the host's own sessions last saw it: one value.

@details See `i_venue_weight_meter.py` for the port that hands it out and for what it cannot say.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WeightReading:
    """The venue's weight at the last answer its sessions saw."""

    #: The used weight of the minute `seen_at` falls in; `None` before any answer.
    used: int | None
    #: The per-minute weight the venue's gate is built against.
    limit: int
    #: Wall-clock seconds (epoch) of the answer `used` came from; `None` with `used`.
    seen_at: float | None
    #: Whether the gate lets a routine request pass now (it is closed from 70 % of `limit`, or by a pause).
    routine_open: bool

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError("a venue's weight limit is positive")
        if (self.used is None) != (self.seen_at is None):
            raise ValueError("`used` and `seen_at` are both known or both unknown")
