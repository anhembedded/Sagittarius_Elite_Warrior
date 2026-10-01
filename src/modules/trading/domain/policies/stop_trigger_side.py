"""`EPIC-028O` — which side of the market a stop price must be on.

@details A stop-limit rests until the stop price trades. A buy stop is
placed above the market and a sell stop below it, on both Binance venues
(Futures `STOP`, Spot `STOP_LOSS_LIMIT`). A stop on the other side is
already crossed: Spot rejects it (`-2010`, "would trigger immediately") and
Futures triggers it at once, so the order fills now instead of waiting. The
app refuses both before anything is sent; the order preview records this
verdict and `ExecuteOrderCommandHandler` acts on it.

A stop exactly at the last price is refused too: it triggers on the next
trade at that price, which is not the wait the user asked for.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.stop_price_check import (
    StopPriceCheck,
)


def check_stop_trigger_side(
    side: OrderSide, stop_price: Decimal, last_price: Decimal
) -> StopPriceCheck:
    """@return `ON_TRIGGER_SIDE` for a buy stop above `last_price` or a
    sell stop below it, `WRONG_SIDE` otherwise."""
    waits = (
        stop_price > last_price if side is OrderSide.BUY else stop_price < last_price
    )
    return StopPriceCheck.ON_TRIGGER_SIDE if waits else StopPriceCheck.WRONG_SIDE
