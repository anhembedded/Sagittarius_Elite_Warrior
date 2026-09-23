from __future__ import annotations

from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame


@dataclass(frozen=True)
class ImportMarketDataCommand:
    """
    @brief Command to load an external candle CSV file into the vault for
    one symbol/interval.
    """

    symbol: str
    interval: TimeFrame
    source_path: str


@dataclass(frozen=True)
class ImportMarketDataResult:
    """
    @brief Typed outcome of executing an ImportMarketDataCommand. `warnings`
    names every row the parser skipped (bad row, not a bad file) — a partial
    import is reported, never silently dropped.
    """

    imported_records: int
    success: bool
    message: str
    warnings: list[str] = field(default_factory=list)
