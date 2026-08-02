from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class MarketData:
    """
    @brief Domain Entity representing a single OHLCV Kline (Candlestick).
    """
    symbol: str
    interval: str
    open_time: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    close_time: datetime
    quote_asset_volume: float
    number_of_trades: int
    taker_buy_base_asset_volume: float
    taker_buy_quote_asset_volume: float
