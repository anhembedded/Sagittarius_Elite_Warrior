"""`EPIC-021M` §4 — the Trading screen's live equity chart: seeded from
`EquityCurveRecorder`'s backlog on construction, appended to live via
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
from Sagittarius_Elite_Warrior.src.application.services.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.domain.events.equity_sampled_event import (
    EquitySampledEvent,
)
from Sagittarius_Elite_Warrior.src.domain.trading.equity_sample import EquitySample
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.equity_chart_adapter import (
    equity_sample_to_candle,
    equity_samples_to_candles,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.trading_presenter import (
    TradingPresenter,
)
from sagittarius_engine.extensions.pyside_mvc.base_view import DEV_MODE_CONFIG_KEY
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
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
def mock_dispatcher():
    return MagicMock()


@pytest.fixture
def mock_thread_manager():
    return MagicMock()


@pytest.fixture
def session_state():
    return TradingSessionState()


@pytest.fixture
def equity_recorder():
    return EquityCurveRecorder()


@pytest.fixture
def container(
    mock_config, mock_dispatcher, mock_thread_manager, session_state, equity_recorder
):
    c = MagicMock()

    def resolve(interface):
        if interface is IConfig:
            return mock_config
        if interface is IDispatcher:
            return mock_dispatcher
        if interface is IThreadManager:
            return mock_thread_manager
        if interface is TradingSessionState:
            return session_state
        if interface is EquityCurveRecorder:
            return equity_recorder
        return MagicMock()

    c.resolve.side_effect = resolve
    return c


@pytest.fixture
def view():
    return MagicMock()


def test_construction_with_an_empty_recorder_seeds_an_empty_chart(
    qapp, view, container
):
    TradingPresenter(view, container)

    view.equity_chart.render_historical_data.assert_called_once_with([])


def test_construction_seeds_the_full_backlog_from_the_recorder(
    qapp, view, container, equity_recorder
):
    equity_recorder.record(_sample(0))
    equity_recorder.record(_sample(1))

    TradingPresenter(view, container)

    view.equity_chart.render_historical_data.assert_called_once_with(
        equity_samples_to_candles([_sample(0), _sample(1)])
    )


def test_equity_sampled_event_appends_one_point_to_the_chart(qapp, view, container):
    presenter = TradingPresenter(view, container)
    view.equity_chart.reset_mock()

    sample = _sample(5)
    presenter._on_equity_sampled(EquitySampledEvent(sample=sample))

    view.equity_chart.append_closed_candle.assert_called_once_with(
        *equity_sample_to_candle(sample)
    )
