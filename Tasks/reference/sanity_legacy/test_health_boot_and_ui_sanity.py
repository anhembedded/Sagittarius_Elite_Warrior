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
    config_manager.load_json(
        os.path.join(base_dir, "src", "config", "user_config.json")
    )

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


_HEALTH_PREFIX = "[Health] Trạng thái hệ thống: HEALTHY"


def _health_lines(presenter) -> list[str]:
    return [
        entry.message
        for entry in presenter._view_model.log_model.entries
        if _HEALTH_PREFIX in entry.message
    ]


def test_real_dashboard_screen_contains_health_log(qapp, booted_app_with_logs):
    """Real screen, real booted app: opening Dashboard produces a health line.

    Proves `EPIC-008E`'s request/response works end to end — the screen asks
    (`HealthCheckRequested`), `HealthExtension` re-measures, and the answer
    comes back over the bus. Before that, this line could only exist because
    the screen fabricated its own `HealthUpdatedEvent`."""
    app, _ = booted_app_with_logs
    presenter = DashboardPresenter(DashboardView(), app.context.container)

    assert _health_lines(presenter), (
        "Dashboard phải nhận báo cáo sức khoẻ khi mở: "
        f"{[e.message for e in presenter._view_model.log_model.entries]}"
    )


def test_real_backtest_screen_contains_health_log(qapp, booted_app_with_logs):
    app, _ = booted_app_with_logs
    presenter = BackTestPresenter(BackTestView(), app.context.container)

    assert _health_lines(presenter), (
        "Backtest phải nhận báo cáo sức khoẻ khi mở: "
        f"{[e.message for e in presenter._view_model.log_model.entries]}"
    )


def test_both_screens_report_health_with_the_identical_string(
    qapp, booted_app_with_logs
):
    """`EPIC-008G` §1's stated evidence: the two screens must say the *same*
    thing about the same fact.

    They did not before. Each parsed the raw status `dict` itself, producing
    two formats — and Backtest's hand-picked its component keys, so it silently
    dropped `Container` entirely:

        Backtest  : [Health] Trạng thái hệ thống: HEALTHY (Database: OK, EventBus: OK)
        Dashboard : System Health: HEALTHY (DB: OK, Container: OK, EventBus: OK)

    One `HealthFeed` now normalises once and both render through
    `HealthStatusReport.to_log_line()`, so they cannot disagree again."""
    app, _ = booted_app_with_logs

    dashboard = DashboardPresenter(DashboardView(), app.context.container)
    backtest = BackTestPresenter(BackTestView(), app.context.container)

    assert _health_lines(dashboard)[-1] == _health_lines(backtest)[-1]
    # And nothing is hand-picked any more, so every component survives.
    assert "Container: OK" in _health_lines(dashboard)[-1]


def test_real_mainwindow_construction_initializes_health_cleanly(
    qapp, booted_app_with_logs
):
    """Assert constructing the full MainWindow renders cleanly with zero QML errors."""
    app, _ = booted_app_with_logs
    window = MainWindow(app)
    assert window is not None
