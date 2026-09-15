"""Reading stored candles: the implementation behind `IHistoricalKlines`.

**Why this file no longer handles a query.** Until `EPIC-025` PR 1.1a it was
`GetHistoricalKlinesQueryHandler`, an `IQueryHandler` six screens and the CLI
dispatched. Its `execute()` returned
`list[MarketData] | dict[str, list[MarketData]]`, chosen by whether the
query's `symbol` field held a `str` or a `list` — a union decided by an
argument's *runtime type*, which `architecture-rule.md` §2.1 forbids, and
which cost every caller three or four unwrapping steps.

PR 1.1a published `IHistoricalKlines` (`load()` and `load_many()`, one return
type each) and moved all six callers onto it. That left `execute()`, the
`GetHistoricalKlinesQuery` dataclass and the dispatcher binding with no
caller anywhere in `src/` — a registration kept alive for a hypothetical
consumer, which is the accidental complexity this epic exists to remove. The
cleanup after 1.1a's review deleted all three, and the class is named for
what it does now.

It still lives under `application/queries/` because it is still the query
side of this module: a read, no writes, nothing dispatched on the way in.
"""

import logging
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    DEFAULT_KLINE_LIMIT,
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)

logger = logging.getLogger("App.QueryHandler")
_TRACE_PREFIX = "BACKTEST_TRACE"

#: How many symbols may be read concurrently. The repository call is I/O
#: bound (SQLite reads, one shard per symbol), so the cap is about not
#: opening dozens of connections for a long symbol list rather than about
#: CPU — a Dev Board with four charts wants four at once, and nobody wants
#: fifty.
_MAX_CONCURRENT_SYMBOL_READS = 10


class StoredKlinesReader(IHistoricalKlines):
    """Reads candles this context has already stored. Never fetches.

    The port implementation *is* this class, per HLD §3.4 — "no pass-through
    object, no extra file per port", the accidental complexity ADR D2 exists
    to avoid. Contrast `IMarketDataSync`, which *is* a separate service: a
    sync has to go through the dispatcher so the in-flight guard and the
    progress events stay on one path. A read has no such machinery.
    """

    def __init__(self, repository: IMarketDataRepository) -> None:
        self.repository = repository

    def load(
        self,
        symbol: str,
        interval: TimeFrame,
        *,
        limit: int = DEFAULT_KLINE_LIMIT,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        newest_first: bool = False,
    ) -> tuple[MarketData, ...]:
        rows = self._read_one(
            symbol,
            interval,
            limit=limit,
            start_time=start_time,
            end_time=end_time,
            newest_first=newest_first,
        )
        self._log_trace("read_complete", symbol=symbol, rows=len(rows))
        return tuple(rows)

    def load_many(
        self,
        symbols: Sequence[str],
        interval: TimeFrame,
        *,
        limit: int = DEFAULT_KLINE_LIMIT,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        newest_first: bool = False,
    ) -> Mapping[str, tuple[MarketData, ...]]:
        requested = list(symbols)
        if not requested:
            # A `ThreadPoolExecutor` for nothing, and `max_workers=0` is not
            # even legal — the empty ask has one honest answer and it needs
            # no thread.
            return {}

        def read(symbol: str) -> tuple[str, tuple[MarketData, ...]]:
            return symbol, tuple(
                self._read_one(
                    symbol,
                    interval,
                    limit=limit,
                    start_time=start_time,
                    end_time=end_time,
                    newest_first=newest_first,
                )
            )

        workers = min(len(requested), _MAX_CONCURRENT_SYMBOL_READS)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            rows = dict(executor.map(read, requested))
        self._log_trace(
            "read_complete_multi",
            symbols=len(rows),
            rows={symbol: len(found) for symbol, found in rows.items()},
        )
        # Every symbol asked for appears, per the port's promise: the caller
        # iterates its own request, and a symbol missing from the answer can
        # never be read as a symbol with no rows.
        return {symbol: rows.get(symbol, ()) for symbol in requested}

    # -- internals -----------------------------------------------------------

    def _read_one(
        self,
        symbol: str,
        interval: TimeFrame,
        *,
        limit: int,
        start_time: datetime | None,
        end_time: datetime | None,
        newest_first: bool,
    ) -> list[MarketData]:
        """One repository read. `newest_first` is the repository's
        `order_by_desc`, renamed at the boundary because the port's callers
        ask for "the newest N", not for a sort direction."""
        return self.repository.get_klines(
            symbol=symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            order_by_desc=newest_first,
        )

    def _log_trace(self, action: str, **fields: object) -> None:
        suffix = " ".join(f"{key}={value!r}" for key, value in fields.items())
        logger.info(f"{_TRACE_PREFIX} action={action} {suffix}".rstrip())
