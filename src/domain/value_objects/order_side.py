from enum import Enum


class OrderSide(str, Enum):
    """
    @brief Which direction a single order submission goes (`EPIC-021C`).
    @details Binance's own order REST parameter (`side`) — always exactly
    BUY or SELL, even for a futures SHORT (expressed as a SELL-to-open in
    one-way mode). Deliberately not `SignalAction`: that enum also carries
    `HOLD`/`SHORT`/`COVER`, a strategy-signal vocabulary that doesn't map
    to "which way should this order's price round."
    """

    BUY = "BUY"
    SELL = "SELL"
