"""`EPIC-021E` — which Binance Futures order type one `Order` uses."""

from __future__ import annotations

from enum import Enum


class OrderType(str, Enum):
    """@brief The exchange order types this app's order model supports.

    @details Narrowed to what this app's trading logic actually sends —
    Binance's futures API supports more (`STOP`, `TAKE_PROFIT`,
    `TRAILING_STOP_MARKET`, ...) that nothing here constructs yet. Add a
    member only when a real call site needs it.
    """

    MARKET = "market"
    LIMIT = "limit"
    STOP_MARKET = "stop_market"
    TAKE_PROFIT_MARKET = "take_profit_market"
