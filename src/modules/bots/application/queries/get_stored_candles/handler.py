"""`BOT-233` — handler for `GetStoredCandlesQuery`.

Reads what is stored for the bot's own venue and counts it against the period, the way a backtest does
(`DataWindow`), so the workbench's "N candles are not stored" and the replay's agree. A period over
`MAX_CANDLES` is refused before anything is loaded: the same bound a Run refuses by.
"""

from __future__ import annotations

from datetime import timedelta

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_stored_candles.query import (
    GetStoredCandlesQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_stored_candles.result import (
    StoredCandles,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest.handler import (
    MAX_CANDLES,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    plan_market_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_simulator import (
    closed_candles,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)


class GetStoredCandlesQueryHandler(IQueryHandler[GetStoredCandlesQuery, StoredCandles]):
    def __init__(self, sources: IMarketDataSources) -> None:
        self._sources = sources

    def execute(self, query: GetStoredCandlesQuery) -> StoredCandles:
        length = timedelta(seconds=query.interval.to_seconds())
        expected = closed_candles(query.start, query.end, length)
        ports = self._sources.ports_for(query.venue.market_data_venue)
        market = plan_market_of(query.venue)
        count = ports.repository.count_klines(
            market, query.symbol, query.interval, query.start, query.end
        )
        if expected > MAX_CANDLES or count > MAX_CANDLES:
            return StoredCandles((), expected, 0, MAX_CANDLES, too_many=True)
        if count == 0:
            return StoredCandles((), expected, 0, MAX_CANDLES)
        candles = tuple(
            ports.history.load(
                market,
                query.symbol,
                query.interval,
                limit=count,
                start_time=query.start,
                end_time=query.end,
            )
        )
        stored = sum(
            1
            for candle in candles
            if candle.open_time >= query.start
            and candle.open_time + length <= query.end
        )
        return StoredCandles(candles, expected, stored, MAX_CANDLES)
