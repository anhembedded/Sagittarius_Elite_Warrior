"""`EPIC-027O` — asset -> last-known USDT price, derived from whatever
symbol prices a screen has already seen (a chart's own last close). Shared
by `DashboardPresenter`/`AccountTabsPresenter` so the same USDT-quoted-only
stripping rule (ADR D9) is not maintained twice.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

#: `EPIC-027N` AC5 — the same literal `arm_strategy/handler.py`/
#: `emergency_stop/handler.py`/`live_order_book_coordinator.py` already carry.
QUOTE_ASSET = "USDT"


def holding_prices_from_symbol_prices(
    prices_by_symbol: Mapping[str, Decimal],
) -> dict[str, Decimal]:
    """A symbol not ending in `QUOTE_ASSET` carries no asset this maps to."""
    return {
        symbol.removesuffix(QUOTE_ASSET): price
        for symbol, price in prices_by_symbol.items()
        if symbol.endswith(QUOTE_ASSET)
    }


def holding_price_for_symbol(symbol: str, price: Decimal | None) -> dict[str, Decimal]:
    """`AccountTabsPresenter`'s wrapper — it only ever knows one symbol's price."""
    return holding_prices_from_symbol_prices(
        {symbol: price} if price is not None else {}
    )
