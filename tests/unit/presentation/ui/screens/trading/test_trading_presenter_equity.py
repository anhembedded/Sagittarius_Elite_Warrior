"""`EPIC-021M` §4 — the Trading screen's live equity chart: seeded from
`IEquityCurve`'s backlog on construction, appended to live via
`EquityFeed`.

Same construction pattern as `test_trading_presenter_toggle.py`: `view` is
a `MagicMock`, so `view.equity_chart.render_historical_data`/
`append_closed_candle` calls are recorded, not rendered for real — the
real `ChartCard` API surface is exercised by `test_trading_view_contract.py`
and `equity_chart_adapter.py`'s own unit tests.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.equity_sample import (
    EquitySample,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.equity_sampled_event import (
    EquitySampledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_equity_curve import (
    IEquityCurve,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.equity_chart_adapter import (
    equity_sample_to_candle,
    equity_samples_to_candles,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.trading_presenter import (
    TradingPresenter,
)
from sagittarius_engine.extensions.pyside_mvc.base_view import DEV_MODE_CONFIG_KEY
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


def _sample(minute: int = 0) -> EquitySample:
    return EquitySample(
        captured_at=datetime(2026, 9, 2, 12, minute, tzinfo=UTC),
        wallet_balance=Decimal("1000.00"),
        unrealized_pnl=Decimal("25.50"),
    )


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get_all.return_value = {
        "DEFAULT_SYMBOLS": ["BTCUSDT"],
        "DEFAULT_INTERVAL": "1m",
    }
    config.get.side_effect = lambda key, default=None, cast=None: (
        True if key == DEV_MODE_CONFIG_KEY else default
    )
    return config


@pytest.fixture
def mock_event_bus():
    return MagicMock()


@pytest.fixture
def container(
    mock_config,
    mock_dispatcher,
    mock_thread_manager,
    trading_session,
    equity_curve,
    mock_event_bus,
    strategy_session,
    strategy_registry,
    make_container,
):
    # `BOT-125` review — one shared fake, so adding a Presenter
    # dependency stops costing one edit per test module.
    return make_container(
        {
            IConfig: mock_config,
            IDispatcher: mock_dispatcher,
            IThreadManager: mock_thread_manager,
            ITradingSession: trading_session,
            IEquityCurve: equity_curve,
            IEventBus: mock_event_bus,
            LiveStrategySession: strategy_session,
            StrategyRegistry: strategy_registry,
        }
    )


@pytest.fixture
def view():
    return MagicMock()


def test_construction_with_an_empty_recorder_seeds_an_empty_chart(
    qapp, view, container
):
    TradingPresenter(view, container)

    view.equity_chart.render_historical_data.assert_called_once_with([])


def test_construction_seeds_the_full_backlog_from_the_curve(
    qapp, view, container, equity_curve
):
    equity_curve.seed([_sample(0), _sample(1)])

    TradingPresenter(view, container)

    view.equity_chart.render_historical_data.assert_called_once_with(
        equity_samples_to_candles([_sample(0), _sample(1)])
    )


def test_a_sample_recorded_right_at_subscribe_time_is_not_missed(
    qapp, view, container, equity_curve, mock_event_bus
):
    """`BUG-100` — before this fix, the chart's seed read happened
    *before* `_connect_engine_events()` subscribed `EquityFeed`. A sample
    recorded strictly between those two points was in neither the seed
    snapshot (recorded after it was read) nor caught by the live
    subscription (which didn't exist yet) — silently missed until the
    next screen re-open. Simulated here by having the mocked event bus's
    own `.on()` registration — the exact moment `EquityFeed` subscribes —
    record a new sample as a side effect, standing in for a real
    `ACCOUNT_UPDATE` landing on the websocket thread at that instant."""
    equity_curve.seed([_sample(0)])
    late_sample = _sample(1)

    def on_subscribe(event_type, _callback):
        if event_type is EquitySampledEvent:
            # The backlog grows strictly between the subscription and the
            # seed read — which is the whole point of `BUG-100`.
            equity_curve.seed([_sample(0), late_sample])

    mock_event_bus.on.side_effect = on_subscribe

    TradingPresenter(view, container)

    view.equity_chart.render_historical_data.assert_called_once_with(
        equity_samples_to_candles([_sample(0), late_sample])
    )


def test_equity_sampled_event_appends_one_point_to_the_chart(qapp, view, container):
    presenter = TradingPresenter(view, container)
    view.equity_chart.reset_mock()

    sample = _sample(5)
    presenter._on_equity_sampled(EquitySampledEvent(sample=sample))

    view.equity_chart.append_closed_candle.assert_called_once_with(
        *equity_sample_to_candle(sample)
    )
