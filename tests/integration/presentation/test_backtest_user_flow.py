"""Deterministic Backtest user-flow tests against the real app container."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
    _FALLBACK_SYMBOL,
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_state import (
    BacktestUiState,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_defaults import (
    default_symbol,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

_BOT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


def _resolve_runtime_symbol() -> str:
    """The symbol the Backtest screen actually opens on, resolved its way.

    A literal here silently stopped matching the screen the moment
    user_config.json stopped shipping DEFAULT_SYMBOLS: the screen fell
    through to its own floor, found nothing seeded under that symbol, and
    went to Binance over the network for candles. Resolving through the
    presenter's own helper and floor keeps the seeded repository and the
    screen on one symbol whether or not the config declares the key.
    """
    config_manager = ConfigManager()
    config_manager.load_json(
        os.path.join(_BOT_ROOT, "src", "config", "user_config.json")
    )
    return default_symbol(config_manager.get_all(), _FALLBACK_SYMBOL)


_RUNTIME_KLINE_COUNT = 240
_RUNTIME_SYMBOL = _resolve_runtime_symbol()
_RUNTIME_INTERVAL = "1h"
_TOOLBAR_TIMEFRAME_INTERVAL = "5m"


# `EPIC-025` PR 0.4a-3: this file used to carry its own 130-line
# `_InMemoryMarketDataRepository` — the third hand-rolled copy of one idea, and
# the exact duplication a verified fake exists to end. It now uses
# `FakeMarketDataRepository`, which ships with the port and passes the same
# contract suite `SQLAlchemyMarketDataRepository` passes, so a divergence
# between what this test assumes and what the real repository does now fails a
# test instead of going unnoticed.


def _make_runtime_klines(interval: str = _RUNTIME_INTERVAL) -> list[MarketData]:
    start = datetime(2026, 8, 1, tzinfo=UTC)
    cadence = timedelta(seconds=TimeFrame(interval).to_seconds())
    return [
        MarketData(
            symbol=_RUNTIME_SYMBOL,
            interval=interval,
            open_time=start + cadence * index,
            open_price=10000.0 + index,
            high_price=10010.0 + index,
            low_price=9990.0 + index,
            close_price=10005.0 + index,
            volume=100.0 + index,
            close_time=start + cadence * (index + 1) - timedelta(seconds=1),
            quote_asset_volume=0.0,
            number_of_trades=1,
            taker_buy_base_asset_volume=0.0,
            taker_buy_quote_asset_volume=0.0,
        )
        for index in range(_RUNTIME_KLINE_COUNT)
    ]


@pytest.fixture
def booted_backtest_app():
    config_manager = ConfigManager()
    config_manager.load_json(
        os.path.join(_BOT_ROOT, "src", "config", "app_config.json")
    )
    config_manager.load_json(
        os.path.join(_BOT_ROOT, "src", "config", "user_config.json")
    )
    app = create_app(config_manager)

    with (
        patch(
            "Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.binance_websocket_service.AsyncClient"
        ),
        patch(
            "Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.binance_websocket_service.BinanceSocketManager"
        ),
    ):
        app.boot()
        yield app
        app.stop()


@pytest.fixture
def backtest_screen(qapp, qtbot, booted_backtest_app):
    booted_backtest_app.context.container.singleton(
        IMarketDataRepository,
        FakeMarketDataRepository(
            _make_runtime_klines() + _make_runtime_klines(_TOOLBAR_TIMEFRAME_INTERVAL)
        ),
    )
    view = BackTestView()
    qtbot.addWidget(view)
    presenter = BackTestPresenter(view, booted_backtest_app.context.container)
    view.show()
    qapp.processEvents()
    yield presenter, view
    presenter._thread_manager.shutdown(wait=True)
    view.close()
    view.deleteLater()


def test_toolbar_popups_open_through_real_signals(backtest_screen, qapp):
    _, view = backtest_screen

    view.top_widget._btn_capital.click()
    qapp.processEvents()
    capital_dialog = view._modals_host._capital
    assert capital_dialog is not None
    # `EPIC-025` PR 4.3f: a `QLineEdit` again, same objectName as both
    # previous versions of this dialog.
    assert capital_dialog._field.objectName() == "txtBacktestCapital"
    assert capital_dialog._field.isVisible() is True

    view.top_widget._btn_bot_params.click()
    qapp.processEvents()
    bot_params_dialog = view._modals_host._strategy_properties
    assert bot_params_dialog is not None
    save_btn = bot_params_dialog.findChild(object, "btnBotParamsSave")
    assert save_btn is not None
    assert save_btn.isVisible() is True


def test_run_button_completes_real_backtest_and_chart_render(backtest_screen, qtbot):
    presenter, view = backtest_screen
    view_model = presenter._view_model
    view_model.selectedTimeframe = _RUNTIME_INTERVAL
    view_model.time_range.preset = "custom"
    view_model.time_range.customStartText = "2026-08-01 00:00"
    view_model.time_range.customEndText = "2026-08-11 00:00"
    log_messages_before = [entry.message for entry in view_model.log_model.entries]
    # EPIC-008G: cả 2 màn giờ render qua HealthStatusReport.to_log_line(), và
    # nó giữ NGUYÊN thứ tự component engine trả về thay vì tự chọn vài khoá —
    # nên đừng assert theo vị trí, assert theo nội dung.
    health_lines = [
        message
        for message in log_messages_before
        if "[Health] System status: HEALTHY" in message
    ]
    assert health_lines, "the Backtest screen must receive a health report on open"
    assert "Database: OK" in health_lines[-1]
    health_count_before = sum("[Health]" in message for message in log_messages_before)

    view.top_widget._btn_run.click()
    qtbot.waitUntil(
        lambda: presenter.fsm.current_state is BacktestUiState.COMPLETED,
        timeout=5000,
    )

    assert view_model.run_result.needsDataSync is False
    assert view._last_klines
    assert view.chart_cards[0].chart_card._raw_history
    log_messages_after = [entry.message for entry in view_model.log_model.entries]
    assert (
        sum("[Health]" in message for message in log_messages_after)
        == health_count_before
    )
    assert any("Starting Backtest" in message for message in log_messages_after)

    view.set_chart_mode(view._chart_mode.EQUITY)
    view.set_chart_mode(view._chart_mode.BOTH)
    view.set_chart_mode(view._chart_mode.OHLC)


def test_chart_toolbar_click_replaces_visible_candles_with_selected_timeframe(
    backtest_screen, qtbot, qml_item
):
    """BUG-008 business regression: a chart-header click changes the chart data.

    The repository deliberately has different 1h/5m sequences.  Merely
    asserting that the 5m button becomes highlighted would reproduce the old
    false-positive test; the accepted result is 5m-spaced candles rendered by
    the visible Backtest ChartCard.

    `EPIC-015` Phase 4 made `ChartToolbar` QML-hosted, so "click the 5m
    button" became a `QTest` click at scene coordinates; `EPIC-025` PR 4.3k
    brought the pills back to `QPushButton`, so it is a click again.
    """
    presenter, view = backtest_screen
    chart = view.chart_cards[0].chart_card
    toolbar = chart.toolbar
    pill = toolbar._row.button_for(_TOOLBAR_TIMEFRAME_INTERVAL)
    assert pill is not None

    with qtbot.waitSignal(view.chartPreviewRendered, timeout=5000):
        pill.click()

    assert presenter._view_model.selectedTimeframe == _TOOLBAR_TIMEFRAME_INTERVAL
    assert len(chart._raw_history) == _RUNTIME_KLINE_COUNT
    assert toolbar._selection.current_code == _TOOLBAR_TIMEFRAME_INTERVAL
    assert chart._raw_history[1][0] - chart._raw_history[0][0] == 300.0
    assert view._last_klines == chart._raw_history


def test_progress_banner_cancel_button_cancels_active_backtest_flow(
    backtest_screen, qtbot, qml_item
):
    from PySide6.QtCore import QPoint

    presenter, view = backtest_screen
    view_model = presenter._view_model
    view_model.selectedTimeframe = _RUNTIME_INTERVAL
    view_model.time_range.preset = "custom"
    view_model.time_range.customStartText = "2026-08-01 00:00"
    view_model.time_range.customEndText = "2026-08-11 00:00"

    # Trigger backtest run via toolbar button
    view.top_widget._btn_run.click()

    # `EPIC-015` Phase 4: the Cancel button lives inside
    # `ProgressBannerWidget`'s QML scene (`kit/ProgressBanner.qml`), reached
    # by `objectName` like every other `Repeater`/QML-scene lookup in this
    # rollout — not a direct `QPushButton` attribute anymore.
    progress_widget = view.top_widget._progress_banner_widget
    assert progress_widget is not None

    # If the backtest is still running or syncing, clicking cancel on the progress banner must cooperatively cancel it
    if presenter.fsm.current_state in (
        BacktestUiState.RUNNING,
        BacktestUiState.SYNCING,
    ):
        cancel_btn = qml_item(progress_widget.root_object, "progressBannerCancelButton")
        assert cancel_btn is not None
        centre = cancel_btn.mapToScene(cancel_btn.boundingRect().center())
        qtbot.mouseClick(
            progress_widget,
            Qt.MouseButton.LeftButton,
            pos=QPoint(int(centre.x()), int(centre.y())),
        )

    qtbot.waitUntil(
        lambda: (
            presenter.fsm.current_state
            in (
                BacktestUiState.IDLE,
                BacktestUiState.CONFIG_DIRTY,
                BacktestUiState.COMPLETED,
            )
        ),
        timeout=5000,
    )
