"""`EPIC-028E` — one fill as the exchange's trade history reports it.

@details One row of Futures `GET /fapi/v1/userTrades` or Spot
`GET /api/v3/myTrades`. The fee is kept in the asset it was charged in: Spot
charges a buy in the base asset, a sell in the quote asset, and either one in
BNB when the account pays fees that way, so converting it here would mean
guessing a price.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide


@dataclass(frozen=True)
class TradeRecord:
    """One fill: what traded, at what price, and what it cost in fees."""

    symbol: str
    #: The exchange's trade id, unique per symbol; orders fills that share a
    #: millisecond.
    trade_id: int
    order_id: int
    side: OrderSide
    price: Decimal
    quantity: Decimal
    #: `price × quantity` as the exchange reports it.
    quote_quantity: Decimal
    fee: Decimal
    fee_asset: str
    time: datetime
    #: Futures only (`realizedPnl`); `None` on Spot, which has no such field.
    realized_pnl: Decimal | None = None
