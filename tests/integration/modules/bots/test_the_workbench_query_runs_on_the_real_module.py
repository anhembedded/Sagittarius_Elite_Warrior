"""`EPIC-040D` — the workbench's one query resolves on the real module's graph, finds the Grid
through the real catalog and replays stored candles, and sends nothing to a bot or an account.

@details `RunBacktestQuery` is bound by `BotsModule.register` (`composition/query_bindings.py`); a
unit test that builds the handler itself proves nothing about that binding (`CS-003`). The market data
is the module's own fake; the watches are the sandbox integration test's."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_backtest import (
    RunBacktestQuery,
    RunBacktestQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_kind_backtester import (
    KindBacktestRequest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_answer import (
    BacktestRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_outcome import (
    BacktestOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_KIND_ID,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.backtest.sandbox_fixtures import (
    SAVED,
    market,
)

from .bots_module_world import registered
from .test_a_sandbox_run_touches_no_bot_order_or_account_on_the_real_module import (
    _CANDLES,
    _T0,
    _VENUE,
    _candles,
    _watch,
)


def _query(kind_id: str) -> RunBacktestQuery:
    return RunBacktestQuery(
        kind_id,
        KindBacktestRequest(
            "BTCUSDT",
            SAVED,
            market().terms,  # type: ignore[arg-type]
            TimeFrame.FIFTEEN_MINUTES,
            _T0,
            _T0 + timedelta(minutes=15 * _CANDLES),
            _VENUE,
        ),
    )


def test_the_bound_handler_replays_the_grid_and_refuses_an_unknown_kind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _module, context = registered(tmp_path / "bots")
    container = context.container
    ports = container.resolve(IMarketDataSources).ports_for(_VENUE.market_data_venue)
    ports.history.seed(_candles(), MarketType.SPOT)
    ports.repository.save_klines(MarketType.SPOT, _candles())
    store = container.resolve(IBotStore)
    stored_before = store.load_all()
    dispatches = _watch(monkeypatch, container.resolve(ICommandDispatcher), "dispatch")
    saves = _watch(monkeypatch, store, "save", "delete")

    handler = container.resolve(
        RunBacktestQuery
    )  # as the dispatcher finds a query's handler
    assert isinstance(handler, RunBacktestQueryHandler)
    answered = handler.execute(_query(GRID_KIND_ID))
    refused = handler.execute(_query("no_such_kind"))

    assert isinstance(answered, BacktestOutcome) and len(answered.bars) == _CANDLES
    assert isinstance(refused, BacktestRefusal)
    assert dispatches == [] and saves == []
    assert store.load_all() == stored_before
