"""BOT-098F6B sanity: the native Backtest chart host embedded in a real
QQuickWidget, against the app's real theme/import bootstrap — mirrors
test_backtest_screen_ui_sanity.py's `booted_app` fixture rather than
hand-rolling a dev-only QQuickView/QApplication setup, since acceptance
criterion 2 explicitly requires proving this does NOT rely on dev-only
environment initialization.
"""

import os
import threading

import pytest
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_adapter import (
    NativeBacktestChartHost,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

_CANDLES = [
    (1_700_000_000.0, 10.0, 12.0, 9.0, 11.0),
    (1_700_000_060.0, 11.0, 13.0, 10.0, 12.0),
    (1_700_000_120.0, 12.0, 14.0, 11.0, 13.0),
]
_VOLUMES = [
    (1_700_000_000.0, 100.0, True),
    (1_700_000_060.0, 200.0, True),
    (1_700_000_120.0, 150.0, False),
]
_MARKERS = [
    (1_700_000_000.0, 10.5, "MUA (LONG)", "#26a69a", "up"),
    (1_700_000_060.0, 11.5, "ĐÓNG LONG", "#ef5350", "down"),
]


@pytest.fixture
def booted_app():
    from unittest.mock import patch

    config_manager = ConfigManager()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_manager.load_json(os.path.join(base_dir, "src", "config", "app_config.json"))
    config_manager.load_json(
        os.path.join(base_dir, "src", "config", "user_config.json")
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


def test_native_backtest_chart_host_constructs_against_the_real_bootstrap(
    qapp, booted_app, request
):
    host = NativeBacktestChartHost.create()
    request.addfinalizer(host.widget.deleteLater)

    assert host.widget is not None


def test_native_backtest_chart_host_receives_candle_indicator_and_marker_snapshots(
    qapp, booted_app, request
):
    host = NativeBacktestChartHost.create()
    request.addfinalizer(host.widget.deleteLater)

    assert host.submit_ohlcv(_CANDLES, _VOLUMES, action_id=1, generation=0) is True
    assert host._ohlcv_revision == 1
    assert host._candle_timestamps_ms == (
        1_700_000_000_000,
        1_700_000_060_000,
        1_700_000_120_000,
    )

    indicator_series = [(0xFF00BFFF, [c[0] for c in _CANDLES], [1.0, 2.0, 3.0])]
    assert host.submit_indicators(indicator_series, action_id=1, generation=1) is True
    assert host._indicator_revision == 1

    assert host.submit_markers(_MARKERS, action_id=1, generation=2) is True
    assert host._marker_revision == 1

    # A stale token (same action, non-increasing generation) must be
    # rejected without touching the native item at all.
    assert host.submit_ohlcv(_CANDLES, _VOLUMES, action_id=1, generation=0) is False
    assert host._ohlcv_revision == 1


def test_native_backtest_chart_host_rejects_a_worker_thread_submission(
    qapp, booted_app, request
):
    host = NativeBacktestChartHost.create()
    request.addfinalizer(host.widget.deleteLater)

    errors: list[BaseException] = []

    def submit_from_worker() -> None:
        try:
            host.submit_ohlcv(_CANDLES, _VOLUMES, action_id=1, generation=0)
        except RuntimeError as error:
            errors.append(error)

    worker = threading.Thread(target=submit_from_worker)
    worker.start()
    worker.join()

    assert len(errors) == 1
    assert "owning GUI thread" in str(errors[0])
    assert host._ohlcv_revision == 0
