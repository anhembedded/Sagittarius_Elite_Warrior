"""An `IMarketDataRepository` over a list — the read side the static backtest
handler uses is real; the write and maintenance side is inert.

Until `EPIC-025A` step 4 ships the verified fake under
`modules/market_data/contracts/testing/`, this is the golden master's own.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Any

from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
    RangeCoverageSnapshot,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.models.data_gap import DataGap
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

_NOT_USED = "not used by the static backtest"


class InMemoryMarketDataRepository(IMarketDataRepository):
    def __init__(self, klines: list[MarketData]) -> None:
        self._klines = list(klines)

    def _rows(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None,
        end_time: datetime | None,
        order_by_desc: bool,
    ) -> list[MarketData]:
        rows = [
            k
            for k in self._klines
            if k.symbol == symbol and k.interval == interval.value
        ]
        if start_time is not None:
            rows = [k for k in rows if k.open_time >= start_time]
        if end_time is not None:
            rows = [k for k in rows if k.open_time <= end_time]
        rows.sort(key=lambda k: k.open_time, reverse=order_by_desc)
        return rows

    def save_klines(self, klines: list[MarketData]) -> None:
        self._klines = list(klines)

    def get_latest_kline_time(
        self, symbol: str, interval: TimeFrame
    ) -> datetime | None:
        rows = self._rows(symbol, interval, None, None, False)
        return rows[-1].open_time if rows else None

    def get_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
        order_by_desc: bool = False,
    ) -> list[MarketData]:
        rows = self._rows(symbol, interval, start_time, end_time, order_by_desc)
        return rows[:limit] if limit is not None else rows

    def count_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> int:
        return len(self.get_klines(symbol, interval, start_time, end_time, limit))

    def stream_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        offset: int | None = None,
        limit: int | None = None,
        order_by_desc: bool = False,
    ) -> Iterator[MarketData]:
        rows = self._rows(symbol, interval, start_time, end_time, order_by_desc)
        if offset is not None:
            rows = rows[offset:]
        if limit is not None:
            rows = rows[:limit]
        yield from rows

    def get_database_status(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(_NOT_USED)

    def get_database_status_for_intervals(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(_NOT_USED)

    def get_range_coverage(self, *args: Any, **kwargs: Any) -> RangeCoverageSnapshot:
        raise NotImplementedError(_NOT_USED)

    def clear_klines(self, symbol: str, interval: TimeFrame | None = None) -> int:
        return 0

    def purge_all(self) -> int:
        return 0

    def list_available_shards(self) -> list[str]:
        return sorted({k.symbol for k in self._klines})

    def vacuum(self, symbol: str | None = None) -> None:
        return None

    def get_gaps(self, symbol: str, interval: TimeFrame) -> list[DataGap]:
        return []

    def has_any_klines(self, symbol: str) -> bool:
        return any(k.symbol == symbol for k in self._klines)
