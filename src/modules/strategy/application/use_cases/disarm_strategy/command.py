"""`EPIC-022B` — "stop running any strategy"."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DisarmStrategyCommand:
    """@brief Command to clear the live strategy (`EPIC-022A`).

    @details No fields — there is exactly one armed strategy per process
    (`BUG-085`), so there is nothing to identify.
    """
