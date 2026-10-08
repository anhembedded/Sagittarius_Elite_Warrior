"""`BUG-191` — what one price update tells a bot: where the price is and where it has been.

A stream pushes a kline update every second or two carrying the close at that
moment; a wick that traded between two pushes survives only in the kline's low
and high. The tick carries all three, plus the bar they belong to, so the exit
rules can see a stop loss or take profit that was crossed and left again. A price
read from the venue's book (a wake from sleep) has no bar and no range: `at`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PriceTick:
    """The last price, and the low and high its bar has traded so far.

    `bar_start` is the kline's open time, `None` for a lone price. The low and
    high are the bar's whole-so-far extremes, *including any before the bot was
    listening*: `GridTickExtremes` decides which of them the bot may act on."""

    last: Decimal
    low: Decimal
    high: Decimal
    bar_start: datetime | None = None

    @staticmethod
    def at(price: Decimal) -> PriceTick:
        """A price with no range of its own."""
        return PriceTick(price, price, price)
