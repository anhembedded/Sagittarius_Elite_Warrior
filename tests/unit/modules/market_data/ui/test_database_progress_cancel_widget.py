"""The Data mode's running task (`EPIC-033J`): its progress is in the window's
status bar (`ui-presentation-rule.md` §10: modeless progress lives there), and
Data → Stop stops it — the action replaced the progress banner's own Cancel
button, which `EPIC-015` and `EPIC-025` PR 4.3l had rebuilt twice.

Renamed from `test_database_progress_cancel_qml.py` at `EPIC-005E` when this
screen went QtWidgets-first."""

from __future__ import annotations

import os
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QLabel, QProgressBar
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_commands import (
    STOP,
    data_commands,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_presenter import (
    DataManagementPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_view import (
    DataManagementView,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.database_screen import (
    DATABASE_ROUTE,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import (
    CANCELLING_CAPTION,
    UIMode,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions

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


def _status(view: DataManagementView) -> tuple[QLabel, QProgressBar]:
    text = next(w for w in view.status_widgets() if w.objectName() == "lblDataTask")
    bar = next(w for w in view.status_widgets() if w.objectName() == "prgDataTask")
    assert isinstance(text, QLabel)
    assert isinstance(bar, QProgressBar)
    return text, bar


def test_progress_shows_in_the_status_bar_and_stop_stops_the_task(
    qapp, database_screen
):
    view, presenter = database_screen
    view_model = presenter._view_model
    actions = bound_actions(
        view, data_commands(DATABASE_ROUTE), presenter.bind_commands
    )
    text, bar = _status(view)

    view_model.set_progress(value=0, maximum=0, visible=False)
    assert not text.isVisibleTo(view)
    assert not bar.isVisibleTo(view)
    assert not actions.action(STOP).isEnabled()

    presenter.fsm.transition_to(UIMode.SYNCING)
    view_model.set_progress(value=25, maximum=100, visible=True, text="Syncing BTCUSDT")
    assert bar.isVisibleTo(view)
    assert bar.value() == 25
    assert text.text() == "Syncing BTCUSDT"
    assert actions.action(STOP).isEnabled()

    actions.action(STOP).trigger()
    qapp.processEvents()

    assert presenter.fsm.current_state == UIMode.CANCELLING
    # A stop has no known duration: the bar stops claiming one and the text
    # says the word.
    assert text.text() == CANCELLING_CAPTION
    assert bar.maximum() == 0
    assert not actions.action(STOP).isEnabled()


def test_fsm_transition_alone_reaches_ui_mode_without_a_manual_set_ui_mode_call(
    qapp, database_screen
):
    """Regression guard: `DataManagementView.apply_ui_mode()` is what
    `BasePresenter._bind_fsm_to_ui`'s FSM callback calls (duck-typed via
    `hasattr` — missing it does not raise, it silently no-ops with just a
    log warning). This drives the FSM directly, with no
    `view_model.set_ui_mode(...)` call: if `apply_ui_mode` were ever removed
    again, `view_model.uiMode` would stay "IDLE" here and this would catch it."""
    view, presenter = database_screen
    view_model = presenter._view_model

    presenter.fsm.transition_to(UIMode.SYNCING)
    qapp.processEvents()

    assert view_model.uiMode == UIMode.SYNCING.value
    assert not view.status_panel._actions["klines"].isEnabled()
