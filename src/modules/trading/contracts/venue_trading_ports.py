"""`EPIC-028B` — one venue's published trading surface, taken together.

@details What another context (strategy) or a screen needs in order to trade
on one venue: shaping and sending orders, the trading switch, the connection
and open positions, and the equity curve. Each port inside is bound to this
bundle's own venue, so a holder cannot address the wrong venue by accident:
the Futures desk holds the Futures bundle and nothing it calls reaches Spot.

Extension cases (`architecture-rule.md` §7.2.1). Each is one new port field
here plus one line in `VenueTradingPortsRegistry`:
- the account summary reader (`EPIC-028D`);
- open orders and order/trade history (`EPIC-028E`);
- a desk's leverage and margin-mode control, should a strategy ever need
  it: `EPIC-028F` delivered it as venue-addressed commands, which a screen
  dispatches, so no field was needed here.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_equity_curve import (
    IEquityCurve,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
    IOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class VenueTradingPorts:
    """The published ports of one venue, each already bound to `venue`."""

    venue: TradingVenue
    order_submission: IOrderSubmission
    trading_session: ITradingSession
    account_snapshot: IAccountSnapshot
    equity_curve: IEquityCurve
