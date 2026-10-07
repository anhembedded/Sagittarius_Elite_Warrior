from enum import Enum


class MarketDataVenue(str, Enum):
    """
    @brief Domain Value Object for which Binance environment market-data reads
    (klines, exchange metadata, the live stream) resolve against.
    @details Since `BUG-172` a screen that acts on a trading venue reads that
    venue's own market: `TradingVenue.market_data_venue` names it, so the chart a
    person looks at is the market their orders fill in. This enum is also the key
    the local candle store, the live stream and every tick are kept apart by —
    testnet candles are never served as mainnet ones.

    `exchange.market_data_venue` (`ConfigKeys.EXCHANGE_MARKET_DATA_VENUE`) is
    read only for the screens that act on no venue (Data mode, a plain
    historical backtest). No key is required for any member: kline and
    `exchangeInfo` reads are public endpoints.

    `MAINNET_PUBLIC` serves Spot Mainnet and Futures Mainnet (a market is picked
    per call, `MarketType`); each testnet has its own member because Spot's
    testnet (`testnet.binance.vision`) and Futures' are two exchanges, and a
    value read from one must never be labelled as the other's.
    """

    MAINNET_PUBLIC = "mainnet_public"
    FUTURES_TESTNET = "futures_testnet"
    SPOT_TESTNET = "spot_testnet"
