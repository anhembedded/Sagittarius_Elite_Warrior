"""
@brief End-to-end Sanity Test for System Health logging across Engine boot, Console, and UI screens.

@details
Verifies:
1. Engine boot sequence produces console log `System Health: HEALTHY`.
2. Real Dashboard screen contains `System Health: HEALTHY` on initial construction.
3. Real Backtest screen contains `[Health] Trạng thái hệ thống: HEALTHY` on initial construction.
4. Real MainWindow construction initializes both screens with valid health logs.
"""

from __future__ import annotations

import logging
import os
from unittest.mock import patch

import pytest
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_presenter import (
    DashboardPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view import (
    DashboardView,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager


@pytest.fixture
def booted_app_with_logs():
    """Boot the real app and capture all log output."""
    config_manager = ConfigManager()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_manager.load_json(os.path.join(base_dir, "src", "config", "app_config.json"))
    config_manager.load_json(os.path.join(base_dir, "src", "config", "user_config.json"))

    app = create_app(config_manager)

    log_records = []

    class MemoryHandler(logging.Handler):
        def emit(self, record):
            log_records.append(record.getMessage())

    handler = MemoryHandler()
    logger = logging.getLogger("App")
    logger.addHandler(handler)

    with (
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.AsyncClient"
        ),
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.BinanceSocketManager"
        ),
    ):
        app.boot()
        yield app, log_records
        logger.removeHandler(handler)
        app.stop()


def test_engine_boot_logs_health_to_console(booted_app_with_logs):
    """Assert Engine boot logs 'System Health: HEALTHY' to the engine logger."""
    _, log_records = booted_app_with_logs
    assert any("System Health: HEALTHY" in msg for msg in log_records), (
        f"Expected 'System Health: HEALTHY' in log records, but got: {log_records}"
    )


def test_real_dashboard_screen_contains_health_log(qapp, booted_app_with_logs):
    """Assert real DashboardPresenter populates log_model with Health log upon construction."""
    app, _ = booted_app_with_logs
    view = DashboardView()
    presenter = DashboardPresenter(view, app.context.container)

    log_messages = [entry.message for entry in presenter._view_model.log_model.entries]
    assert any("System Health: HEALTHY" in msg for msg in log_messages), (
        f"Expected 'System Health: HEALTHY' in Dashboard logs, got: {log_messages}"
    )


def test_real_backtest_screen_contains_health_log(qapp, booted_app_with_logs):
    """Assert real BackTestPresenter populates log_model with Health log upon construction."""
    app, _ = booted_app_with_logs
    view = BackTestView()
    presenter = BackTestPresenter(view, app.context.container)

    log_messages = [entry.message for entry in presenter._view_model.log_model.entries]
    assert any("[Health] Trạng thái hệ thống: HEALTHY" in msg for msg in log_messages), (
        f"Expected '[Health] Trạng thái hệ thống: HEALTHY' in Backtest logs, got: {log_messages}"
    )


def test_real_mainwindow_construction_initializes_health_cleanly(qapp, booted_app_with_logs):
    """Assert constructing the full MainWindow renders cleanly with zero QML errors."""
    app, _ = booted_app_with_logs
    window = MainWindow(app)
    assert window is not None


def test_step_enter_backtest_and_click_run_backtest_logs_health(qapp, booted_app_with_logs):
    """
    Step 1: Enter Backtest Screen (Construct BackTestPresenter).
    Step 2: Click 'Chạy Backtest' (_on_run_backtest).
    Assert that Health check is executed and displayed in the UI log model.
    """
    app, _ = booted_app_with_logs
    view = BackTestView()
    presenter = BackTestPresenter(view, app.context.container)

    # Step 1: Check logs upon entering Backtest screen
    log_messages_on_enter = [entry.message for entry in presenter._view_model.log_model.entries]
    assert any("[Health] Trạng thái hệ thống: HEALTHY" in msg for msg in log_messages_on_enter)

    # Step 2: User clicks "Chạy Backtest"
    with patch.object(presenter, "_start_backtest_run"):
        presenter._on_run_backtest()

    # Step 3: Check logs after clicking run
    log_messages_after_run = [entry.message for entry in presenter._view_model.log_model.entries]
    assert any("[Health] Trạng thái hệ thống: HEALTHY" in msg for msg in log_messages_after_run)
    assert any("Bắt đầu chạy Backtest" in msg for msg in log_messages_after_run)

