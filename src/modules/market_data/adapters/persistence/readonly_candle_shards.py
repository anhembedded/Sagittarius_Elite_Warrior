"""`EPIC-047H` — the host's candle store, opened read-only by a second process (the bridge).

@details Plain `sqlite3`, not SQLAlchemy: the bridge is started by `sshd` for each session and must start
fast, and this file is imported by it (`modules/market_data/link.py`). The store is WAL (`SqliteShardManager`),
so a reader never blocks the host's writer and the host's commits show at once (assumption A9, measured
2026-10-27: 3 553 reads against 57 226 commits, 0 errors). The file is opened `mode=ro`: this class cannot
create a shard, write a row or leave a lock; a shard that does not exist is `shard_found=False`, not a new file.

**One account must be able to open the store read-only.** Opening a WAL file read-only needs the `-shm` file or
write access to its directory; the `sew` account's access is the owner's check (`EPIC-047H`, owner steps).
A shard that cannot be opened is reported as not found, with the cause at DEBUG.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.shard_name import (
    shard_name,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.venue_subdirectory import (
    venue_subdirectory,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.closed_candle_window import (
    MAX_WINDOW_CANDLES,
    CandleWindow,
    StoredCandle,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.Database")

_SQLITE_TIME = "%Y-%m-%d %H:%M:%S.%f"
_TIMEOUT_S = 0.25
_COLUMNS = "open_time, open_price, high_price, low_price, close_price, volume"


def shard_path(base: Path, venue: TradingVenue, symbol: str) -> Path:
    """Where the host keeps `symbol`'s candles for `venue`: the venue's directory and the market-qualified shard."""
    market = venue.market_type
    if market is None:
        raise ValueError(f"{venue.value} trades no market and has no candles")
    return (
        base
        / venue_subdirectory(venue.market_data_venue)
        / f"{shard_name(market, symbol)}.db"
    )


class ReadOnlyCandleShards:
    def __init__(self, base: Path) -> None:
        self._base = base

    def window(
        self,
        venue: TradingVenue,
        symbol: str,
        timeframe: str,
        limit: int,
        before: datetime | None,
    ) -> CandleWindow:
        path = shard_path(self._base, venue, symbol)
        rows = self._rows(
            path, symbol, timeframe, min(max(limit, 1), MAX_WINDOW_CANDLES), before
        )
        if rows is None:
            return CandleWindow(venue, symbol, timeframe, (), False, False)
        newest_first = rows[:limit]
        return CandleWindow(
            venue,
            symbol,
            timeframe,
            tuple(_candle(row) for row in reversed(newest_first)),
            shard_found=True,
            older_available=len(rows) > limit,
        )

    def _rows(
        self,
        path: Path,
        symbol: str,
        timeframe: str,
        limit: int,
        before: datetime | None,
    ) -> list[tuple[object, ...]] | None:
        if not path.is_file():
            return None
        cutoff = "" if before is None else " AND open_time < ?"
        arguments: list[object] = [symbol, timeframe]
        if before is not None:
            arguments.append(before.astimezone(UTC).strftime(_SQLITE_TIME))
        arguments.append(limit + 1)
        try:
            with closing(
                sqlite3.connect(
                    f"{path.as_uri()}?mode=ro", uri=True, timeout=_TIMEOUT_S
                )
            ) as db:
                return db.execute(
                    f"SELECT {_COLUMNS} FROM klines WHERE symbol = ? AND interval = ?{cutoff} "  # noqa: S608 - the only interpolated parts are fixed strings above
                    "ORDER BY open_time DESC LIMIT ?",
                    arguments,
                ).fetchall()
        except sqlite3.Error as failure:
            logger.debug("Candle shard %s not read: %s", path.name, failure)
            return None


def _candle(row: tuple[object, ...]) -> StoredCandle:
    opened = datetime.strptime(str(row[0]), _SQLITE_TIME).replace(tzinfo=UTC)
    prices = [Decimal(str(value)) for value in row[1:]]
    return StoredCandle(opened, *prices)
