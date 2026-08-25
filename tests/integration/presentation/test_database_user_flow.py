"""Deterministic Database screen (Storage Vault) user-flow integration tests."""

from __future__ import annotations

import os
import time
from unittest.mock import Mock, patch

import pytest
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_presenter import (
    DataManagementPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view import (
    DataManagementView,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def database_app_context(qapp, qtbot, monkeypatch, request):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    config_manager = ConfigManager()
    bot_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    )
    config_manager.load_json(os.path.join(bot_root, "src", "config", "app_config.json"))
    config_manager.load_json(
        os.path.join(bot_root, "src", "config", "user_config.json")
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
        mock_client = Mock(spec=IExchangeClient)

        def mock_get_historical_klines(*args, **kwargs):
            time.sleep(0.3)
            return []

        mock_client.get_historical_klines.side_effect = mock_get_historical_klines
        # `Mock(spec=...)` chỉ ràng buộc *tên* method, không ràng buộc kiểu trả
        # về: method chưa cấu hình trả về một `Mock` thô, nên handler thật gọi
        # `len()` hay lặp lên nó là nổ. Hai lỗi đó vẫn xảy ra từ trước nhưng
        # **vô hình** — chúng đi vào `logging` chuẩn thay vì file log của app.
        # `EPIC-008G` §4 (bus có `ILogger` thật) làm chúng hiện ra ở bước
        # "Run Log Scan" của gate. Cấu hình nốt để test không tạo lỗi giả.
        mock_client.get_available_symbols.return_value = ["BTCUSDT", "ETHUSDT"]
        mock_client.stream_historical_klines.return_value = iter(())
        app.context.container.singleton(IExchangeClient, mock_client)

        view = DataManagementView()
        qtbot.addWidget(view)
        presenter = DataManagementPresenter(view, app.context.container)
        view.show()
        qapp.processEvents()

        yield view, presenter, mock_client

        presenter._thread_manager.shutdown(wait=True)
        view.close()
        view.deleteLater()
        app.stop()


def test_database_cancel_button_cancels_active_sync_flow(
    qapp, qtbot, database_app_context
):
    """EPIC-005E: DataManagementView is QtWidgets now (was QmlHostView) —
    `btnCancelSync` is a real QPushButton (`view._btn_cancel_sync`), not a
    QML item reached through `qml_item()`/`quick_widget.rootObject()`."""
    view, presenter, _ = database_app_context
    cancel_btn = view._btn_cancel_sync
    view_model = presenter._view_model

    # Start single sync
    view_model.selectedSymbol = "BTCUSDT"
    view_model.selectedInterval = "1m"
    view_model.requestSync()
    qapp.processEvents()

    # Wait until in SYNCING state and progress is visible
    qtbot.waitUntil(lambda: presenter.fsm.current_state == UIMode.SYNCING, timeout=2000)
    assert cancel_btn.isVisible() is True
    assert cancel_btn.isEnabled() is True

    # Click Cancel
    cancel_btn.click()
    qapp.processEvents()

    # FSM transitions through CANCELLING then back to IDLE
    qtbot.waitUntil(lambda: presenter.fsm.current_state == UIMode.IDLE, timeout=5000)
    assert view_model.progressVisible is False
