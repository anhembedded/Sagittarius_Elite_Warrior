from enum import Enum


class MarketType(str, Enum):
    """
    @brief Which Binance market segment a candle, order or account belongs to
    — spot trading, or one of the two futures markets.

    @details `EPIC-027A` gave every storage/sync call an explicit market.
    Screens with no market selector yet (Phase 1: everything except the
    Backtest screen's future `EPIC-027D` picker) pin their calls to `SPOT` —
    what they have always read and fetched — rather than defaulting silently.
    Call sites say so with a one-line comment pointing here, not a repeated
    paragraph.
    """

    SPOT = "spot"
    FUTURES_USD_M = "futures_usd_m"
    FUTURES_COIN_M = "futures_coin_m"
