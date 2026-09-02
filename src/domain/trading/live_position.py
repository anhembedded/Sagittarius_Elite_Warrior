"""`EPIC-021E` — one open position on the exchange, as read back from it.

@details Distinct from `_OpenPosition`
(`domain/backtesting/paper_exchange.py`): that one is a backtest
simulation's private bookkeeping, mutated tick-by-tick by this app's own
matching logic. `LivePosition` is a read-only snapshot of exchange-reported
truth, refreshed by `ITradingClient.get_positions()` — this app never
computes any of its fields, only parses them off the wire.

@par Scope this file deliberately does not cover (`EPIC-021E` §2.5)
- **Funding rate**: excluded from PnL here — see
  `test_live_pnl_excludes_funding_fees` for the locked behaviour and the
  condition under which that would need to change.
- **Liquidation price**: `liquidation_price` is read verbatim from the
  exchange, never computed by this app — its own `LiquidationPrice` type
  exists so a locally-computed `Decimal` can never be passed where an
  exchange-reported one belongs.
- **Hedge mode**: this type assumes One-way (`positionSide=BOTH`), matching
  the assumption `EPIC-021D` already enforces at the connection-check door
  (`ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED`). Direction is derived
  from the sign of `position_amt` rather than carried as its own field,
  because One-way mode has exactly one position per symbol — a separate
  `side` field would just be a second, independently-mutable copy of what
  the sign already says.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import NewType

from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)

#: Distinct from a bare `Decimal` so a locally-computed price can never be
#: passed where an exchange-reported liquidation price belongs.
LiquidationPrice = NewType("LiquidationPrice", Decimal)


@dataclass(frozen=True)
class LivePosition:
    """Immutable snapshot of one open position, as last reported by the
    exchange."""

    symbol: str
    #: Signed: positive is long, negative is short (see `side`). Zero never
    #: appears here — a flat position is simply absent from
    #: `ITradingClient.get_positions()`'s result, not a `LivePosition` with
    #: `position_amt == 0`.
    position_amt: Decimal
    entry_price: Decimal
    mark_price: Decimal
    unrealized_pnl: Decimal
    leverage: int
    margin_type: MarginType
    liquidation_price: LiquidationPrice | None
    updated_at: datetime

    @property
    def side(self) -> PositionSide:
        return PositionSide.LONG if self.position_amt > 0 else PositionSide.SHORT
