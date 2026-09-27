from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.export_file_format import (
    ExportFileFormat,
)


@dataclass(frozen=True)
class ExportMarketDataCommand:
    """
    @brief Command to write one symbol/interval's stored klines to a file
    on disk, for use outside this application (quant research in Pandas,
    a spreadsheet, another backtester).
    """

    symbol: str
    interval: TimeFrame
    market: MarketType
    destination_path: str
    file_format: ExportFileFormat
    start_time: datetime | None = None
    end_time: datetime | None = None


@dataclass(frozen=True)
class ExportMarketDataResult:
    """
    @brief Typed outcome of executing an ExportMarketDataCommand.
    """

    exported_records: int
    success: bool
    message: str
