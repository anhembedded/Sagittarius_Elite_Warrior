from abc import ABC, abstractmethod
from datetime import datetime
from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame


class IExchangeClient(ABC):
    """
    @brief Port for communicating with an external cryptocurrency exchange.
    """

    @abstractmethod
    def get_historical_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_str: str | datetime,
        end_str: str | datetime | None = None,
    ) -> list[MarketData]:
        """
        @brief Fetches historical kline data for a symbol.
        @param symbol The trading pair symbol (e.g. BTCUSDT)
        @param interval The timeframe interval (e.g. 1m)
        @param start_str The start time string (e.g. '1 day ago UTC') or datetime
        @param end_str Optional end time string or datetime
        @return A list of MarketData entities.
        """
        pass
