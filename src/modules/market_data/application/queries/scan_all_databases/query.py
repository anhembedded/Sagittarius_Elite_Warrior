from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    DatabaseStatusSnapshot,
)

_STATUS_OK = "OK"


@dataclass(frozen=True)
class DatabaseStatusDTO:
    """
    @brief Data Transfer Object for a single database scan result.
    @details Carries one symbol/interval pair's status as values — the UI's
    formatter writes the dates and the count (`EPIC-033N`); only the status
    sentence is decided here. Used as the result element type of
    ScanAllDatabasesQuery and GetDatabaseStatusQuery.
    """

    symbol: str
    interval: str
    #: `None` when the shard holds no candle.
    first_record: datetime | None
    last_record: datetime | None
    total_candles: int
    gaps: int
    status_text: str

    @classmethod
    def from_snapshot(
        cls, symbol: str, interval: str, snapshot: DatabaseStatusSnapshot
    ) -> DatabaseStatusDTO:
        """
        @brief Builds the DTO from a raw repository snapshot.
        @details Single source of truth for the "OK" vs "N gaps found!" status text,
        so GetDatabaseStatusQueryHandler and ScanAllDatabasesQueryHandler can't
        drift apart on how a status is described.
        """
        status_text = (
            _STATUS_OK if snapshot.gaps == 0 else f"{snapshot.gaps} gaps found!"
        )
        return cls(
            symbol=symbol,
            interval=interval,
            first_record=snapshot.first_record,
            last_record=snapshot.last_record,
            total_candles=snapshot.total_candles,
            gaps=snapshot.gaps,
            status_text=status_text,
        )


@dataclass(frozen=True)
class ScanAllDatabasesQuery:
    """
    @brief Query to scan the database status for provided symbol/interval combinations.
    @details If symbols is empty, automatically discovers all storage shards on disk.
    If intervals is empty, defaults to standard intervals.
    """

    symbols: list[str] = field(default_factory=list)
    intervals: list[str] = field(default_factory=list)
    cancellation_requested: Callable[[], bool] | None = field(
        default=None,
        repr=False,
        compare=False,
    )
