"""`EPIC-022B` — the outcome of one `DisarmStrategyCommand`."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DisarmStrategyBlockReason(str, Enum):
    """@brief Why the strategy was not cleared."""

    #: This app has a position open on the symbol the strategy trades
    #: (`EPIC-034C`). Disarming would leave it with no strategy planning its
    #: exit. It was refused while trading was ON; with no switch the cause
    #: itself refuses. `EmergencyStopCommand` remains the unconditional way out.
    POSITION_OPEN = "position_open"


@dataclass(frozen=True)
class DisarmStrategyResult:
    disarmed: bool
    block_reason: DisarmStrategyBlockReason | None = None
