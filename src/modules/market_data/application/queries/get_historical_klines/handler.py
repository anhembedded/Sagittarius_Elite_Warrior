import logging
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    DEFAULT_KLINE_LIMIT,
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)

logger = logging.getLogger("App.QueryHandler")
_TRACE_PREFIX = "BACKTEST_TRACE"


class GetHistoricalKlinesQueryHandler(
    IQueryHandler[
        GetHistoricalKlinesQuery, list[MarketData] | dict[str, list[MarketData]]
    ],
    IHistoricalKlines,
):
    """Reads stored candles: this module's own query handler, and the
    implementation of the `IHistoricalKlines` port other contexts resolve.

    **Two bases, no third class.** HLD §3.4 says a port implementation may be
    the existing handler itself — "no pass-through object, no extra file per
    port", because a dozen one-method delegating classes is the accidental
    complexity ADR D2 exists to avoid. `execute()` stays exactly as it was for
    the module's own dispatches; `load()` and `load_many()` are the published
    surface, and both call the same two private methods `execute()` calls.

    Contrast `IMarketDataSync`, which *is* a separate service
    (`MarketDataSyncService`): a sync has to go through the dispatcher so the
    in-flight guard and the progress events stay on one path. A query has no
    such machinery — nothing happens on the way in — so the extra hop would
    buy nothing.
    """

    def __init__(self, repository: IMarketDataRepository) -> None:
        self.repository = repository

    def _log_trace(self, action: str, **fields: object) -> None:
        suffix = " ".join(f"{key}={value!r}" for key, value in fields.items())
        logger.info(f"{_TRACE_PREFIX} action={action} {suffix}".rstrip())

    def execute(
        self, query: GetHistoricalKlinesQuery
    ) -> list[MarketData] | dict[str, list[MarketData]]:
        self._log_trace(
            "query_execute_start",
            symbol=query.symbol,
            timeframe=query.interval.value,
            limit=query.limit,
            start=query.start_time,
            end=query.end_time,
            order_by_desc=query.order_by_desc,
        )
        logger.debug(
            f"Handling GetHistoricalKlinesQuery for {query.symbol} at {query.interval.value} (limit={query.limit})"
        )

        if isinstance(query.symbol, list):
            return self._execute_multi(query, query.interval)

        return self._execute_single(query, query.interval)

    def _execute_multi(
        self, query: GetHistoricalKlinesQuery, interval_vo: TimeFrame
    ) -> dict[str, list[MarketData]]:
        results = {}

        def fetch_symbol(sym: str) -> tuple[str, list[MarketData]]:
            return sym, self.repository.get_klines(
                symbol=sym,
                interval=interval_vo,
                start_time=query.start_time,
                end_time=query.end_time,
                limit=query.limit,
                order_by_desc=query.order_by_desc,
            )

        max_workers = min(len(query.symbol), 10) if query.symbol else 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for sym, klines in executor.map(fetch_symbol, query.symbol):
                results[sym] = klines
        self._log_trace(
            "query_execute_complete_multi",
            symbols=len(results),
            rows={sym: len(klines) for sym, klines in results.items()},
        )
        return results

    def _execute_single(
        self, query: GetHistoricalKlinesQuery, interval_vo: TimeFrame
    ) -> list[MarketData]:
        result = self.repository.get_klines(
            symbol=query.symbol,
            interval=interval_vo,
            start_time=query.start_time,
            end_time=query.end_time,
            limit=query.limit,
            order_by_desc=query.order_by_desc,
        )
        self._log_trace(
            "query_execute_complete",
            symbol=query.symbol,
            rows=len(result),
        )
        return result

    # -- IHistoricalKlines: the published surface -----------------------------

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
        return tuple(
            self._execute_single(
                GetHistoricalKlinesQuery(
                    symbol=symbol,
                    interval=interval,
                    limit=limit,
                    start_time=start_time,
                    end_time=end_time,
                    order_by_desc=newest_first,
                ),
                interval,
            )
        )

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
            # `_execute_multi` would build a `ThreadPoolExecutor` for nothing,
            # and `max_workers=0` is not even legal — the empty ask has one
            # honest answer and it needs no thread.
            return {}
        rows = self._execute_multi(
            GetHistoricalKlinesQuery(
                symbol=requested,
                interval=interval,
                limit=limit,
                start_time=start_time,
                end_time=end_time,
                order_by_desc=newest_first,
            ),
            interval,
        )
        # Every symbol asked for appears, per the port's promise: the caller
        # iterates its own request, and a symbol missing from the answer can
        # never be read as a symbol with no rows.
        return {symbol: tuple(rows.get(symbol, ())) for symbol in requested}
