"""`EPIC-048B` — "which venues may a bot be on, and is each one connected"."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GetVenueChoicesQuery:
    """Asks for every venue some bot kind runs on; takes nothing, the host knows its venues."""
