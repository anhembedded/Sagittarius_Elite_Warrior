"""`EPIC-033D` — the Dev Board's Reload history, Enable live trading,
Emergency stop and New order are actions.

The commands the trading module really contributes (`real_contributions`),
bound by `bind_dev_board_commands` into the Engine's real `ActionRegistry`
through the window's own `action_descriptor`, over a real
`DashboardQmlViewModel`.
"""

from __future__ import annotations

from unittest.mock import Mock

from PySide6.QtCore import QObject
from PySide6.QtGui import QKeySequence
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dashboard_screen import (
    DASHBOARD_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dashboard_view_model import (
    DashboardQmlViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dev_board_command_binding import (
    bind_dev_board_commands,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dev_board_commands import (
    EMERGENCY_STOP,
    ENABLE_TRADING,
    NEW_ORDER,
    RELOAD_HISTORY,
    dev_board_commands,
)
from Sagittarius_Elite_Warrior.tests.command_actions import (
    RecordingConfirmer,
    bound_actions,
)
from Sagittarius_Elite_Warrior.tests.conftest import real_contributions


class _Board:
    """A view model, its commands bound, and what they asked for."""

    def __init__(self) -> None:
        self.owner = QObject()
        self.view_model = DashboardQmlViewModel()
        self.confirmer = RecordingConfirmer()
        self.orders_opened = 0
        self.requests: list[str] = []
        self.view_model.loadHistoryRequested.connect(
            lambda: self.requests.append("reload")
        )
        self.view_model.toggleRequested.connect(lambda: self.requests.append("toggle"))
        self.view_model.emergencyStopRequested.connect(
            lambda: self.requests.append("stop")
        )
        self.registry = bound_actions(
            self.owner,
            dev_board_commands(DASHBOARD_ROUTE),
            lambda binder: bind_dev_board_commands(
                binder, self.view_model, self._open_order
            ),
            self.confirmer,
        )

    def _open_order(self) -> None:
        self.orders_opened += 1


def test_the_trading_module_contributes_the_dev_boards_commands() -> None:
    modes = {
        command.command_id: command.mode
        for command in real_contributions(Mock()).commands()
    }

    for command_id in (RELOAD_HISTORY, ENABLE_TRADING, EMERGENCY_STOP, NEW_ORDER):
        assert modes[command_id] == DASHBOARD_ROUTE


def test_each_action_makes_the_request_its_button_made(qapp) -> None:
    board = _Board()

    for command_id in (RELOAD_HISTORY, ENABLE_TRADING, EMERGENCY_STOP, NEW_ORDER):
        board.registry.action(command_id).trigger()

    assert board.requests == ["reload", "toggle", "stop"]
    assert board.orders_opened == 1
    assert [asked.title for asked in board.confirmer.asked] == ["Emergency stop"]
    assert board.registry.unbound() == ()


def test_reload_follows_the_controls_and_the_running_load(qapp) -> None:
    board = _Board()
    reload = board.registry.action(RELOAD_HISTORY)
    assert reload.isEnabled()

    board.view_model.set_history_loading(True)
    assert not reload.isEnabled()

    board.view_model.set_history_loading(False)
    board.view_model.set_ui_mode("LIVE")
    assert not reload.isEnabled()


def test_enable_follows_the_session(qapp) -> None:
    board = _Board()
    enable = board.registry.action(ENABLE_TRADING)

    board.view_model.set_trading_state(enabled=False, busy=True)
    assert not enable.isEnabled()

    board.view_model.set_trading_state(enabled=True, busy=False)
    assert enable.isEnabled()
    assert enable.isChecked()


def test_new_order_is_f9_and_asks_for_input(qapp) -> None:
    board = _Board()
    new_order = board.registry.action(NEW_ORDER)

    assert new_order.shortcut() == QKeySequence("F9")
    assert new_order.text().endswith("…")
