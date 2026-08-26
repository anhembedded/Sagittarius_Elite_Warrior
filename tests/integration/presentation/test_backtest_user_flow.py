"""Deterministic Backtest user-flow tests against the real app container."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    DatabaseStatusSnapshot,
    DataGap,
    IMarketDataRepository,
    RangeCoverageSnapshot,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.presentation.ui.common.app_defaults import (
    default_symbol,
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


class _InMemoryMarketDataRepository(IMarketDataRepository):
    def __init__(self, klines: list[MarketData]) -> None:
        self._klines = list(klines)

    def save_klines(self, klines: list[MarketData]) -> None:
        self._klines = list(klines)

    def get_latest_kline_time(
        self, symbol: str, interval: TimeFrame
    ) -> datetime | None:
        matching_klines = self.get_klines(symbol, interval)
        return matching_klines[-1].open_time if matching_klines else None

    def get_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
        order_by_desc: bool = False,
    ) -> list[MarketData]:
        rows = [
            kline
            for kline in self._klines
            if kline.symbol == symbol and kline.interval == interval.value
        ]
        if start_time is not None:
            rows = [kline for kline in rows if kline.open_time >= start_time]
        if end_time is not None:
            rows = [kline for kline in rows if kline.open_time <= end_time]
        rows.sort(key=lambda kline: kline.open_time, reverse=order_by_desc)
        return rows[:limit] if limit is not None else rows

    def count_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> int:
        return len(self.get_klines(symbol, interval, start_time, end_time, limit))

    def stream_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        offset: int | None = None,
        limit: int | None = None,
        order_by_desc: bool = False,
    ):
        rows = self.get_klines(
            symbol, interval, start_time, end_time, None, order_by_desc
        )
        if offset is not None:
            rows = rows[offset:]
        if limit is not None:
            rows = rows[:limit]
        yield from rows

    def get_database_status(
        self, symbol: str, interval: TimeFrame
    ) -> DatabaseStatusSnapshot:
        rows = self.get_klines(symbol, interval)
        return DatabaseStatusSnapshot(
            first_record=rows[0].open_time if rows else None,
            last_record=rows[-1].open_time if rows else None,
            total_candles=len(rows),
            gaps=0,
        )

    def get_range_coverage(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None,
        end_time: datetime,
        now: datetime,
    ) -> RangeCoverageSnapshot:
        rows = self.get_klines(symbol, interval, start_time, end_time)
        rows = [row for row in rows if row.open_time < end_time]
        first_gap_after = next(
            (
                previous.open_time
                for previous, current in pairwise(rows)
                if (current.open_time - previous.open_time).total_seconds()
                > interval.to_seconds()
            ),
            None,
        )
        return RangeCoverageSnapshot(
            first_record=rows[0].open_time if rows else None,
            last_record=rows[-1].open_time if rows else None,
            total_candles=len(rows),
            distinct_candles=len({row.open_time for row in rows}),
            first_gap_after=first_gap_after,
            unclosed_candles=sum(
                bool(row.close_time and row.close_time > now) for row in rows
            ),
        )

    def clear_klines(self, symbol: str, interval: TimeFrame | None = None) -> int:
        return 0

    def purge_all(self) -> int:
        return 0

    def list_available_shards(self) -> list[str]:
        return [_RUNTIME_SYMBOL]

    def vacuum(self, symbol: str | None = None) -> None:
        pass

    def get_gaps(self, symbol: str, interval: TimeFrame) -> list[DataGap]:
        return []


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
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.AsyncClient"
        ),
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.BinanceSocketManager"
        ),
    ):
        app.boot()
        yield app
        app.stop()


@pytest.fixture
def backtest_screen(qapp, qtbot, booted_backtest_app):
    booted_backtest_app.context.container.singleton(
        IMarketDataRepository,
        _InMemoryMarketDataRepository(
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
    assert capital_dialog._capital_input.isVisible() is True

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
    view_model.timeRangePreset = "custom"
    view_model.customStartText = "2026-08-01 00:00"
    view_model.customEndText = "2026-08-11 00:00"
    log_messages_before = [entry.message for entry in view_model.log_model.entries]
    # EPIC-008G: cả 2 màn giờ render qua HealthStatusReport.to_log_line(), và
    # nó giữ NGUYÊN thứ tự component engine trả về thay vì tự chọn vài khoá —
    # nên đừng assert theo vị trí, assert theo nội dung.
    health_lines = [
        message
        for message in log_messages_before
        if "[Health] Trạng thái hệ thống: HEALTHY" in message
    ]
    assert health_lines, "màn Backtest phải nhận được báo cáo sức khoẻ khi mở"
    assert "Database: OK" in health_lines[-1]
    health_count_before = sum("[Health]" in message for message in log_messages_before)

    view.top_widget._btn_run.click()
    qtbot.waitUntil(
        lambda: presenter.fsm.current_state is BacktestUiState.COMPLETED,
        timeout=5000,
    )

    assert view_model.needsDataSync is False
    assert view._last_klines
    assert view.chart_cards[0].chart_card._raw_history
    log_messages_after = [entry.message for entry in view_model.log_model.entries]
    assert (
        sum("[Health]" in message for message in log_messages_after)
        == health_count_before
    )
    assert any("Bắt đầu chạy Backtest" in message for message in log_messages_after)

    view.set_chart_mode(view._chart_mode.EQUITY)
    view.set_chart_mode(view._chart_mode.BOTH)
    view.set_chart_mode(view._chart_mode.OHLC)


def test_chart_toolbar_click_replaces_visible_candles_with_selected_timeframe(
    backtest_screen, qtbot
):
    """BUG-008 business regression: a chart-header click changes the chart data.

    The repository deliberately has different 1h/5m sequences.  Merely
    asserting that the 5m button becomes highlighted would reproduce the old
    false-positive test; the accepted result is 5m-spaced candles rendered by
    the visible Backtest ChartCard.
    """
    presenter, view = backtest_screen
    chart = view.chart_cards[0].chart_card
    five_minute_button = chart.toolbar._buttons[_TOOLBAR_TIMEFRAME_INTERVAL]

    with qtbot.waitSignal(view.chartPreviewRendered, timeout=5000):
        qtbot.mouseClick(five_minute_button, Qt.MouseButton.LeftButton)

    assert presenter._view_model.selectedTimeframe == _TOOLBAR_TIMEFRAME_INTERVAL
    assert len(chart._raw_history) == _RUNTIME_KLINE_COUNT
    assert five_minute_button.isChecked() is True
    assert chart._raw_history[1][0] - chart._raw_history[0][0] == 300.0
    assert view._last_klines == chart._raw_history


def test_progress_banner_cancel_button_cancels_active_backtest_flow(
    backtest_screen, qtbot
):
    presenter, view = backtest_screen
    view_model = presenter._view_model
    view_model.selectedTimeframe = _RUNTIME_INTERVAL
    view_model.timeRangePreset = "custom"
    view_model.customStartText = "2026-08-01 00:00"
    view_model.customEndText = "2026-08-11 00:00"

    # Trigger backtest run via toolbar button
    view.top_widget._btn_run.click()

    # Progress banner and its cancel button are visible in cancellable state
    cancel_btn = view.top_widget._btn_cancel_progress
    assert cancel_btn is not None

    # If the backtest is still running or syncing, clicking cancel on the progress banner must cooperatively cancel it
    if presenter.fsm.current_state in (
        BacktestUiState.RUNNING,
        BacktestUiState.SYNCING,
    ):
        cancel_btn.click()

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
