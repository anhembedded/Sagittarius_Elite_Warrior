from enum import Enum


class MarketType(str, Enum):
    """
    @brief Domain Value Object representing which Binance market segment a
    screen targets — spot trading, or one of the two futures markets.
    """

    SPOT = "spot"
    FUTURES_USD_M = "futures_usd_m"
    FUTURES_COIN_M = "futures_coin_m"
