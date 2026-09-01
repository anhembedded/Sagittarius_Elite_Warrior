from enum import Enum


class MarketDataVenue(str, Enum):
    """
    @brief Domain Value Object for which Binance venue market-data reads
    (klines, exchange metadata) resolve against (`EPIC-021A`).
    @details Independent of `TradingVenue` — a user may read chart/backtest
    data from `MAINNET_PUBLIC` while orders go to `FUTURES_TESTNET`, since
    those answer two unrelated questions ("is my chart trustworthy" vs.
    "where does my money go"; see `EPIC-021`'s ADR §2). No key is required
    for `MAINNET_PUBLIC` — kline/exchangeInfo reads are public endpoints.
    """

    MAINNET_PUBLIC = "mainnet_public"
    FUTURES_TESTNET = "futures_testnet"
