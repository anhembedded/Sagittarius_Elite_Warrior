from __future__ import annotations

import os
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_presenter import (
    DataManagementPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view import (
    DataManagementView,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def database_screen(qapp, request):
    mock_thread_mgr = Mock()
    mock_dispatcher = Mock()
    container = Mock()

    def resolve_mock(interface):
        from sagittarius_engine.extensions.pyside_mvc.base_view import (
            DEV_MODE_CONFIG_KEY,
        )
        from sagittarius_engine.interfaces.i_config import IConfig
        from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
        from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

        if interface == IThreadManager:
            return mock_thread_mgr
        if interface == IDispatcher:
            return mock_dispatcher
        if interface == IConfig:
            mock_config = Mock()
            mock_config.get_all.return_value = {}
            mock_config.get.side_effect = lambda key, default=None: (
                True if key == DEV_MODE_CONFIG_KEY else default
            )
            return mock_config
        return Mock()

    container.resolve.side_effect = resolve_mock
    view = DataManagementView()
    view.resize(1400, 800)
    view.show()
    qapp.processEvents()
    presenter = DataManagementPresenter(view, container)
    qapp.processEvents()
    request.addfinalizer(view.deleteLater)
    return view, presenter


def test_database_cancel_button_visibility_and_interaction(
    qapp, qml_item, database_screen
):
    view, presenter = database_screen
    root = view.quick_widget.rootObject()
    view_model = presenter._view_model

    cancel_btn = qml_item(root, "btnCancelSync")
    assert cancel_btn is not None

    # 1. In IDLE mode with progressVisible=False -> cancel button is not visible
    view_model.set_progress(value=0, maximum=0, visible=False)
    qapp.processEvents()
    assert cancel_btn.property("visible") is False

    # 2. When syncing is active (progressVisible=True, SYNCING mode) -> cancel button is visible & enabled
    view_model.set_progress(value=10, maximum=100, visible=True)
    presenter.fsm.transition_to(UIMode.SYNCING)
    view_model.set_ui_mode(UIMode.SYNCING.value)
    qapp.processEvents()

    assert cancel_btn.property("visible") is True
    assert cancel_btn.property("enabled") is True
    assert "Hủy" in cancel_btn.property("text")

    # 3. Clicking cancel button emits cancelRequested and transitions to CANCELLING
    cancel_signal_called = False

    def on_cancel():
        nonlocal cancel_signal_called
        cancel_signal_called = True

    view_model.cancelRequested.connect(on_cancel)
    cancel_btn.clicked.emit()
    qapp.processEvents()

    assert cancel_signal_called is True
    assert presenter.fsm.current_state == UIMode.CANCELLING

    # In CANCELLING mode, button is disabled and displays "Đang hủy..."
    assert cancel_btn.property("enabled") is False
    assert cancel_btn.property("text") == "Đang hủy..."
