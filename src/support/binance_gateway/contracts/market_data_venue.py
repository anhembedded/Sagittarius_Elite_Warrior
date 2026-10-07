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

    A screen that acts on no venue (Data mode, the Market mode, a plain
    historical backtest, the CLI) reads `DEFAULT_MARKET_DATA_VENUE`, the public
    mainnet: testnet data has short history and fake liquidity, so it is useless
    for research. No key is required for any member: kline and `exchangeInfo`
    reads are public endpoints.

    `MAINNET_PUBLIC` serves Spot Mainnet and Futures Mainnet (a market is picked
    per call, `MarketType`); each testnet has its own member because Spot's
    testnet (`testnet.binance.vision`) and Futures' are two exchanges, and a
    value read from one must never be labelled as the other's.
    """

    MAINNET_PUBLIC = "mainnet_public"
    FUTURES_TESTNET = "futures_testnet"
    SPOT_TESTNET = "spot_testnet"


#: The market of every screen that acts on no trading venue. Not configurable:
#: the setting that chose it was removed because only the mainnet's history is
#: worth researching on.
DEFAULT_MARKET_DATA_VENUE = MarketDataVenue.MAINNET_PUBLIC
