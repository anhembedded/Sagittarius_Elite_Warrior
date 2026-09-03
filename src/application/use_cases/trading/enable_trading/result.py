"""`EPIC-021G` — the outcome of one `EnableTradingCommand`."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.domain.trading.live_position import LivePosition
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order


class EnableTradingBlockReason(str, Enum):
    """@brief Why trading did not turn on — named, never a bare `False`."""

    #: `TradingVenue != FUTURES_TESTNET` — trading itself is off at the
    #: config level (ADR §3), the same gate `ExecuteOrderCommand` also
    #: checks.
    TRADING_VENUE_DISABLED = "trading_venue_disabled"
    #: `EPIC-021D`'s connection check did not come back reachable and
    #: fully ready (includes Hedge Mode — `ConnectionFailureKind.
    #: HEDGE_MODE_UNSUPPORTED` already covers "reachable but not usable").
    CONNECTION_NOT_READY = "connection_not_ready"
    #: The exchange already has an open position this app has no record
    #: of — refused outright rather than silently adopted or auto-closed
    #: (`EPIC-021G` §2.4, ADR §4). The user decides what to do next.
    UNEXPECTED_POSITIONS = "unexpected_positions"
    #: `BUG-088` — something else (a `disable()`, another `enable()`, an
    #: order, a reconciliation) mutated `TradingSessionState` while this
    #: command's own reconciliation network calls were in flight, most
    #: often an Emergency Stop that ran mid-reconciliation. Refused rather
    #: than applied — silently turning trading back on right after an
    #: Emergency Stop would defeat the whole point of that button.
    SUPERSEDED_BY_CONCURRENT_STATE_CHANGE = "superseded_by_concurrent_state_change"


@dataclass(frozen=True)
class EnableTradingResult:
    enabled: bool
    block_reason: EnableTradingBlockReason | None
    reconciled_positions: tuple[LivePosition, ...]
    reconciled_open_orders: tuple[Order, ...]
