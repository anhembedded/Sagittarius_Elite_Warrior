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
    qapp, qtbot, qml_item, database_app_context
):
    view, presenter, _ = database_app_context
    root = view.quick_widget.rootObject()
    view_model = presenter._view_model

    cancel_btn = qml_item(root, "btnCancelSync")
    assert cancel_btn is not None

    # Start single sync
    view_model.selectedSymbol = "BTCUSDT"
    view_model.selectedInterval = "1m"
    view_model.requestSync()
    qapp.processEvents()

    # Wait until in SYNCING state and progress is visible
    qtbot.waitUntil(lambda: presenter.fsm.current_state == UIMode.SYNCING, timeout=2000)
    assert cancel_btn.property("visible") is True
    assert cancel_btn.property("enabled") is True

    # Click Cancel
    cancel_btn.clicked.emit()
    qapp.processEvents()

    # FSM transitions through CANCELLING then back to IDLE
    qtbot.waitUntil(lambda: presenter.fsm.current_state == UIMode.IDLE, timeout=5000)
    assert view_model.progressVisible is False
