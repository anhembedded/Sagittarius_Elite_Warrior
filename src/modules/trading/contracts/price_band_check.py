"""`BUG-146` — whether an order's price sits inside the venue's price band."""

from __future__ import annotations

from enum import Enum


class PriceBandCheck(str, Enum):
    """@brief The verdict `price_band_policy.check_price_band` gives and
    `OrderPreview.price_band_check` carries."""

    #: Inside `PERCENT_PRICE_BY_SIDE` for its side at the last price.
    INSIDE = "inside"
    #: Outside: the exchange rejects it with `-1013 Filter failure:
    #: PERCENT_PRICE_BY_SIDE`.
    OUTSIDE = "outside"
