"""`EPIC-040D` — one query runs any kind's backtest, found through the catalog by the kind's id."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_kind_backtester import (
    GridKindBacktester,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_backtest import (
    RunBacktestQuery,
    RunBacktestQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest import (
    GridBacktestAnswer,
    GridBacktestRefusal,
    RunGridBacktestQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_kind_backtester import (
    IKindBacktester,
    KindBacktestRequest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_answer import (
    BacktestAnswer,
    BacktestCancelled,
    BacktestRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_KIND_ID,
    GridKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    TERMS,
)

_T0 = datetime(2026, 9, 1, tzinfo=UTC)


class _Recording(IKindBacktester):
    def __init__(self, answer: BacktestAnswer) -> None:
        self._answer = answer
        self.requests: list[KindBacktestRequest] = []

    def run(self, request: KindBacktestRequest) -> BacktestAnswer:
        self.requests.append(request)
        return self._answer


def _request() -> KindBacktestRequest:
    return KindBacktestRequest(
        "BTCUSDT",
        CONFIG,
        TERMS,
        TimeFrame.FIFTEEN_MINUTES,
        _T0,
        _T0 + timedelta(hours=6),
        TradingVenue.SPOT_TESTNET,
    )


def _handler(backtester: IKindBacktester | None) -> RunBacktestQueryHandler:
    kind = GridKind(None, GridThresholds(), backtester)  # type: ignore[arg-type]
    return RunBacktestQueryHandler(BotKindCatalog([kind]))


def test_the_kinds_own_backtester_answers_the_request_it_was_given() -> None:
    answer = BacktestCancelled(1, 2)
    backtester = _Recording(answer)
    request = _request()

    result = _handler(backtester).execute(RunBacktestQuery(GRID_KIND_ID, request))

    assert result is answer
    assert backtester.requests == [request]


def test_a_kind_the_catalog_does_not_know_is_refused_in_words() -> None:
    result = _handler(_Recording(BacktestCancelled(0, 0))).execute(
        RunBacktestQuery("dca", _request())
    )

    assert isinstance(result, BacktestRefusal)
    assert "'dca'" in result.reason and not result.missing_candles


def test_a_kind_with_no_backtest_is_refused_in_words() -> None:
    result = _handler(None).execute(RunBacktestQuery(GRID_KIND_ID, _request()))

    assert isinstance(result, BacktestRefusal)
    assert "has no backtest" in result.reason


class _GridQuery(IQueryHandler[RunGridBacktestQuery, GridBacktestAnswer]):
    def __init__(self) -> None:
        self.queries: list[RunGridBacktestQuery] = []

    def execute(self, query: RunGridBacktestQuery) -> GridBacktestAnswer:
        self.queries.append(query)
        return GridBacktestRefusal("no candles", missing_candles=True)


def test_the_grid_is_found_by_its_kind_id_and_its_adapter_runs_the_grid_query() -> None:
    grid_query = _GridQuery()
    request = _request()

    result = _handler(GridKindBacktester(grid_query)).execute(
        RunBacktestQuery(GRID_KIND_ID, request)
    )

    assert result == BacktestRefusal("no candles", missing_candles=True)
    assert (grid_query.queries[0].symbol, grid_query.queries[0].start) == (
        request.symbol,
        request.start,
    )
