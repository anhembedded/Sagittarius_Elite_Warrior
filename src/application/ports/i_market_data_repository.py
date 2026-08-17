from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


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

    first_record: datetime | None
    last_record: datetime | None
    total_candles: int
    gaps: int


@dataclass(frozen=True)
class RangeCoverageSnapshot:
    """Small SQLite aggregate used to validate one half-open candle range."""

    first_record: datetime | None
    last_record: datetime | None
    total_candles: int
    distinct_candles: int
    first_gap_after: datetime | None
    unclosed_candles: int


class IMarketDataRepository(ABC):
    """
    @brief Port for storing and retrieving market data.
    """

    @abstractmethod
    def save_klines(self, klines: list[MarketData]) -> None:
        """
        @brief Saves a batch of klines to the repository.
        """

    @abstractmethod
    def get_latest_kline_time(
        self, symbol: str, interval: TimeFrame
    ) -> datetime | None:
        """
        @brief Retrieves the open_time of the most recent kline stored for a given symbol and interval.
        @return The datetime of the latest kline, or None if no data exists.
        """

    @abstractmethod
    def get_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
        order_by_desc: bool = False,
    ) -> list[MarketData]:
        """
        @brief Retrieves historical klines from the repository.
        """

    @abstractmethod
    def get_database_status(
        self, symbol: str, interval: TimeFrame
    ) -> DatabaseStatusSnapshot:
        """
        @brief Gets database status for a specific symbol/interval.
        @return A DatabaseStatusSnapshot with first_record, last_record, total_candles, gaps.
        """

    @abstractmethod
    def get_range_coverage(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None,
        end_time: datetime,
        now: datetime,
    ) -> RangeCoverageSnapshot:
        """Aggregate coverage facts for ``[start_time, end_time)``."""
