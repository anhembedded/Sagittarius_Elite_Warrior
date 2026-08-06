from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class DatabaseStatusDTO:
    """
    @brief Data Transfer Object for a single database scan result.
    @details Carries pre-formatted, display-ready status for one symbol/interval pair.
    Used as the result element type of ScanAllDatabasesQuery.
    """

    symbol: str
    interval: str
    first_record: str
    last_record: str
    total_candles: str
    gaps: str
    status_text: str


@dataclass(frozen=True)
class ScanAllDatabasesQuery:
    """
    @brief Query to scan the database status for all provided symbol/interval combinations.
    @details Eliminates the Domain Leakage anti-pattern where the Presenter was
    orchestrating a nested loop of individual GetDatabaseStatusQuery dispatches.
    The Handler owns the iteration logic; the Presenter simply dispatches once.
    """

    symbols: List[str]
    intervals: List[str]
