"""`BOT-126` — `TradingPresenter._handle_market_tick` used to filter a
`MarketTickEvent` by `symbol` alone, exactly the fault `BUG-085` fixed for
`MarketTickEventHandler`. That was harmless while `ILiveStreamService` was
one process-wide stream (no two intervals for the same symbol could ever
be live at once); `BOT-126`'s per-owner subscriptions made it possible for
real (Dev Board and this screen each own their own), so this locks the
fix: a tick for the active symbol at a DIFFERENT interval must never reach
the chart.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from Sagittarius_Elite_Warrior.src.application.services.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.trading_presenter import (
    TradingPresenter,
)
from sagittarius_engine.extensions.pyside_mvc.base_view import DEV_MODE_CONFIG_KEY
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


def _market_data(symbol: str = "BTCUSDT", interval: str = "1m") -> MarketData:
    dt = datetime(2023, 1, 1, tzinfo=UTC)
    return MarketData(
        symbol=symbol,
        interval=interval,
        open_time=dt,
        open_price=100.0,
        high_price=110.0,
        low_price=90.0,
        close_price=105.0,
        volume=1000.0,
        close_time=dt,
        quote_asset_volume=105000.0,
        number_of_trades=50,
        taker_buy_base_asset_volume=500.0,
        taker_buy_quote_asset_volume=52500.0,
        is_closed=True,
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
def container(
    mock_config,
    mock_dispatcher,
    mock_thread_manager,
    session_state,
    equity_recorder,
    strategy_session,
    strategy_registry,
    make_container,
):
    return make_container(
        {
            IConfig: mock_config,
            IDispatcher: mock_dispatcher,
            IThreadManager: mock_thread_manager,
            TradingSessionState: session_state,
            EquityCurveRecorder: equity_recorder,
            LiveStrategySession: strategy_session,
            StrategyRegistry: strategy_registry,
        }
    )


@pytest.fixture
def view():
    return MagicMock()


@pytest.fixture
def presenter(qapp, view, container, mock_thread_manager):
    p = TradingPresenter(view, container)
    mock_thread_manager.submit.reset_mock()
    return p


def test_a_tick_for_the_active_symbol_at_a_different_interval_is_ignored(
    presenter, view
):
    presenter._active_symbol = "BTCUSDT"
    presenter._active_interval = "1m"
    view.chart.append_closed_candle.reset_mock()

    event = MarketTickEvent(market_data=_market_data("BTCUSDT", "5m"))
    presenter._handle_market_tick(event)

    view.chart.append_closed_candle.assert_not_called()


def test_a_tick_for_the_active_symbol_and_interval_reaches_the_chart(presenter, view):
    presenter._active_symbol = "BTCUSDT"
    presenter._active_interval = "1m"
    view.chart.append_closed_candle.reset_mock()

    event = MarketTickEvent(market_data=_market_data("BTCUSDT", "1m"))
    presenter._handle_market_tick(event)

    view.chart.append_closed_candle.assert_called_once()


def test_a_tick_for_a_different_symbol_is_still_ignored_regardless_of_interval(
    presenter, view
):
    presenter._active_symbol = "BTCUSDT"
    presenter._active_interval = "1m"
    view.chart.append_closed_candle.reset_mock()

    event = MarketTickEvent(market_data=_market_data("ETHUSDT", "1m"))
    presenter._handle_market_tick(event)

    view.chart.append_closed_candle.assert_not_called()
