"""`BOT-190` — when what an exit left is dust, as the stop already treats it.

The Spot close keeps a base worth less than the venue's minimum notional (`closer_spot.py`), and
neither close can send less than one market step (`market_slices.base_slices`). The exit report asks
the same question of what is still held after a closing slice was booked, so it tells the exit once
nothing more will be sold.
"""

from __future__ import annotations

from decimal import Decimal


def is_exit_dust(
    held: Decimal,
    price: Decimal | None,
    market_step: Decimal,
    min_notional: Decimal | None,
) -> bool:
    """Whether `held` (a quantity, either sign) is one the stop would not sell any more.

    @param price The bot's last price; without one only the step judges.
    @param min_notional The venue's minimum order value where a base below it is kept as dust
        (Spot); `None` where a reduce-only close ignores it (a position venue).
    """
    quantity = abs(held)
    if quantity < market_step:
        return True
    return (
        min_notional is not None
        and price is not None
        and quantity * price < min_notional
    )
