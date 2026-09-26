from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.domain.data_gap import DataGap


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
    @details `EPIC-027A` — every method takes an explicit `market: MarketType`.
    Spot and Futures candles of the same symbol and interval are stored and
    read independently; there is no default market a caller falls back on.
    """

    @abstractmethod
    def save_klines(self, market: MarketType, klines: list[MarketData]) -> None:
        """
        @brief Saves a batch of klines to the repository.
        @details `klines` must all belong to `market` — a single call writes to
        one market's shards. A caller mixing markets in one batch is a caller
        bug, not something this port infers from the candles themselves
        (candles carry no market field; see the ADR's own finding).
        """

    @abstractmethod
    def get_latest_kline_time(
        self, market: MarketType, symbol: str, interval: TimeFrame
    ) -> datetime | None:
        """
        @brief Retrieves the open_time of the most recent kline stored for a given
        market, symbol and interval.
        @return The datetime of the latest kline, or None if no data exists.
        """

    @abstractmethod
    def get_klines(
        self,
        market: MarketType,
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
    def count_klines(
        self,
        market: MarketType,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> int:
        """
        @brief Counts historical klines matching the given filters, without
        materializing any of them.
        @details BUG-025 — lets a caller learn how many rows a range holds
        before deciding how to stream it (e.g. computing an in-sample /
        out-of-sample split point), instead of loading the whole range into
        RAM just to call `len()` on it.
        """

    @abstractmethod
    def stream_klines(
        self,
        market: MarketType,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        offset: int | None = None,
        limit: int | None = None,
        order_by_desc: bool = False,
    ) -> Iterator[MarketData]:
        """
        @brief Streams historical klines matching the given filters without
        holding the full result set in RAM at once.
        @details BUG-025 — the Backtest data path's counterpart to
        `get_klines()`. Same filters plus `offset`, since a caller that
        already knows the row count (via `count_klines()`) needs to fetch
        specific sub-ranges (e.g. an out-of-sample tail) without re-reading
        rows it already streamed. Does not replace `get_klines()`, which
        every other, small/bounded caller keeps using unchanged.
        """

    @abstractmethod
    def get_database_status(
        self, market: MarketType, symbol: str, interval: TimeFrame
    ) -> DatabaseStatusSnapshot:
        """
        @brief Gets database status for a specific market/symbol/interval.
        @return A DatabaseStatusSnapshot with first_record, last_record, total_candles, gaps.
        """

    @abstractmethod
    def get_database_status_for_intervals(
        self, market: MarketType, symbol: str, intervals: list[TimeFrame]
    ) -> dict[str, DatabaseStatusSnapshot]:
        """
        @brief Gets database status for every interval of one market/symbol in a
        single call.
        @details BUG-078 — lets a caller scanning many intervals of the same symbol
        (e.g. `ScanAllDatabasesQueryHandler`) do it over one underlying connection
        instead of one per interval, since a symbol's intervals all live in the same
        shard. Keyed by `TimeFrame.value`.
        @return Dict mapping each requested interval's value to its snapshot.
        """

    @abstractmethod
    def get_range_coverage(
        self,
        market: MarketType,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None,
        end_time: datetime,
        now: datetime,
    ) -> RangeCoverageSnapshot:
        """Aggregate coverage facts for ``[start_time, end_time)``."""

    @abstractmethod
    def clear_klines(
        self, market: MarketType, symbol: str, interval: TimeFrame | None = None
    ) -> int:
        """
        @brief Deletes klines for a given market/symbol and optional interval.
        @return The number of deleted records.
        """

    @abstractmethod
    def purge_all(self) -> int:
        """
        @brief Purges all market data databases / shards, across every market.
        @return Total number of shards or records purged.
        """

    @abstractmethod
    def list_available_shards(self, market: MarketType) -> list[str]:
        """
        @brief Lists all symbol names that have an existing storage shard for one
        market on disk.
        @return List of symbol names (e.g. ['BTCUSDT', 'ETHUSDT']).
        """

    @abstractmethod
    def vacuum(self, market: MarketType, symbol: str | None = None) -> None:
        """
        @brief Optimizes SQLite storage by running VACUUM on one market's specified
        or all shards.
        """

    @abstractmethod
    def get_gaps(
        self, market: MarketType, symbol: str, interval: TimeFrame
    ) -> list[DataGap]:
        """
        @brief Scans and returns all detected gaps in historical market data for a
        market/symbol/interval.
        @return Ordered list of DataGap objects.
        """

    @abstractmethod
    def has_any_klines(self, market: MarketType, symbol: str) -> bool:
        """
        @brief Whether a market/symbol's shard holds at least one kline, in any
        interval.
        @details BUG-078 — deliberately interval-agnostic (unlike `get_database_status`),
        so a caller deciding whether a shard is safe to delete never misjudges "empty"
        against only a curated interval subset (e.g. the default 6 shown in the UI) while
        the shard actually holds data at some other interval.
        """
