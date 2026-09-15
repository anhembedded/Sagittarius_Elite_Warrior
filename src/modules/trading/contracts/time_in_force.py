"""`EPIC-021E` — how long a `LIMIT` order stays open before the exchange
cancels it unfilled."""

from __future__ import annotations

from enum import Enum


class TimeInForce(str, Enum):
    """@brief Binance's `timeInForce` order parameter.

    @details Only meaningful for `OrderType.LIMIT` — `MARKET`,
    `STOP_MARKET`, and `TAKE_PROFIT_MARKET` orders resolve immediately and
    never carry one; `Order.time_in_force` is `None` for those.
    """

    #: Good-Til-Canceled — stays open until filled or explicitly canceled.
    GTC = "GTC"
    #: Immediate-Or-Cancel — fills whatever it can at once, cancels the rest.
    IOC = "IOC"
    #: Fill-Or-Kill — fills entirely at once, or is canceled entirely.
    FOK = "FOK"
