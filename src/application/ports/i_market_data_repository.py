from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame


@dataclass(frozen=True)
class DatabaseStatusSnapshot:
    """
    @brief Raw, typed result of a database status lookup — replaces the untyped
    dict this port used to return (Primitive Obsession).
    @details Deliberately NOT the display-formatted DatabaseStatusDTO used by the
    query handlers: keeping repository results in their natural types (datetime,
    int) keeps formatting/"OK" vs "N gaps found!" text out of the infrastructure
    layer. See DatabaseStatusDTO.from_snapshot() for the mapping.
    """

    first_record: Optional[datetime]
    last_record: Optional[datetime]
    total_candles: int
    gaps: int


class IMarketDataRepository(ABC):
    """
    @brief Port for storing and retrieving market data.
    """

    @abstractmethod
    def save_klines(self, klines: list[MarketData]) -> None:
        """
        @brief Saves a batch of klines to the repository.
        """
        pass

    @abstractmethod
    def get_latest_kline_time(
        self, symbol: str, interval: TimeFrame
    ) -> Optional[datetime]:
        """
        @brief Retrieves the open_time of the most recent kline stored for a given symbol and interval.
        @return The datetime of the latest kline, or None if no data exists.
        """
        pass

    @abstractmethod
    def get_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None,
        order_by_desc: bool = False,
    ) -> list[MarketData]:
        """
        @brief Retrieves historical klines from the repository.
        """
        pass

    @abstractmethod
    def get_database_status(
        self, symbol: str, interval: TimeFrame
    ) -> DatabaseStatusSnapshot:
        """
        @brief Gets database status for a specific symbol/interval.
        @return A DatabaseStatusSnapshot with first_record, last_record, total_candles, gaps.
        """
        pass
