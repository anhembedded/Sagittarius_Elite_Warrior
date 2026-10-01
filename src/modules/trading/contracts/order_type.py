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
    #: `EPIC-028O` (ADR O3) — a limit order that rests only once the stop
    #: price trades. Binance spells it per venue (Futures `STOP`, Spot
    #: `STOP_LOSS_LIMIT`), so each payload mapper owns its wire name rather
    #: than sending this member's name.
    STOP_LIMIT = "stop_limit"
    #: `BUG-091` — the honest answer for a Binance order type this app's
    #: own construction never sends (`LIQUIDATION`, `TRAILING_STOP_MARKET`,
    #: ...) but the account-wide user data stream can still report for an
    #: order this app did not place itself. Same catch-all idiom
    #: `OrderStatus.UNKNOWN` uses, for the same reason: a parser must
    #: never lose an update just because it can't name every field on it.
    UNKNOWN = "unknown"
