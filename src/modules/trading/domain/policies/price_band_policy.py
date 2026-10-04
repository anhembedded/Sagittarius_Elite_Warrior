"""`BUG-146` — whether a priced order sits inside Binance Spot's
`PERCENT_PRICE_BY_SIDE` band.

@details Binance accepts a BUY between `bid_down` and `bid_up` times the
symbol's average price over `avgPriceMins`, and a SELL between `ask_down` and
`ask_up` times it. This app judges against the last price it knows, the same
reference the stop gate uses (`stop_trigger_side.py`): close to that average
in a normal market. Both edges are accepted, as Binance's own inclusive bounds
are.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.price_band_check import (
    PriceBandCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    PercentPriceBand,
)


def check_price_band(
    band: PercentPriceBand, side: OrderSide, price: Decimal, last_price: Decimal
) -> PriceBandCheck:
    """@return `INSIDE` when `price` is within `side`'s band at `last_price`."""
    if side is OrderSide.BUY:
        low, high = band.bid_down, band.bid_up
    else:
        low, high = band.ask_down, band.ask_up
    inside = last_price * low <= price <= last_price * high
    return PriceBandCheck.INSIDE if inside else PriceBandCheck.OUTSIDE
