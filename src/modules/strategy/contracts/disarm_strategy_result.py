"""`EPIC-022B` — the outcome of one `DisarmStrategyCommand`."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DisarmStrategyBlockReason(str, Enum):
    """@brief Why the strategy was not cleared."""

    #: Live trading is currently ON. Disarming would leave trading
    #: "enabled" with nothing generating signals via the strategy path,
    #: and an open position would be left with no strategy planning its
    #: exit. `EnableTradingCommand` itself no longer requires an armed
    #: strategy to turn trading on at all (`BUG-112` — manual trading
    #: needs none), so this handler's refusal is now the only place left
    #: guarding this direction; `EmergencyStopCommand` remains the
    #: unconditional way out of a live session regardless.
    TRADING_IS_ENABLED = "trading_is_enabled"


@dataclass(frozen=True)
class DisarmStrategyResult:
    disarmed: bool
    block_reason: DisarmStrategyBlockReason | None = None
