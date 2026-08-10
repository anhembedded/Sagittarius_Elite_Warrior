from dataclasses import dataclass

from Binace_Bot.src.application.ports.i_market_data_repository import (
    DatabaseStatusSnapshot,
)

_STATUS_OK = "OK"


@dataclass(frozen=True)
class DatabaseStatusDTO:
    """
    @brief Data Transfer Object for a single database scan result.
    @details Carries pre-formatted, display-ready status for one symbol/interval pair.
    Used as the result element type of ScanAllDatabasesQuery and GetDatabaseStatusQuery.
    """

    symbol: str
    interval: str
    first_record: str
    last_record: str
    total_candles: str
    gaps: str
    status_text: str

    @classmethod
    def from_snapshot(
        cls, symbol: str, interval: str, snapshot: DatabaseStatusSnapshot
    ) -> "DatabaseStatusDTO":
        """
        @brief Builds a display-ready DTO from a raw repository snapshot.
        @details Single source of truth for the "OK" vs "N gaps found!" status text and
        string formatting, so GetDatabaseStatusQueryHandler and ScanAllDatabasesQueryHandler
        can't drift apart on how a status is presented.
        """
        status_text = (
            _STATUS_OK if snapshot.gaps == 0 else f"{snapshot.gaps} gaps found!"
        )
        return cls(
            symbol=symbol,
            interval=interval,
            first_record=str(snapshot.first_record or "N/A"),
            last_record=str(snapshot.last_record or "N/A"),
            total_candles=str(snapshot.total_candles),
            gaps=str(snapshot.gaps),
            status_text=status_text,
        )


@dataclass(frozen=True)
class ScanAllDatabasesQuery:
    """
    @brief Query to scan the database status for all provided symbol/interval combinations.
    @details Eliminates the Domain Leakage anti-pattern where the Presenter was
    orchestrating a nested loop of individual GetDatabaseStatusQuery dispatches.
    The Handler owns the iteration logic; the Presenter simply dispatches once.
    """

    symbols: list[str]
    intervals: list[str]
