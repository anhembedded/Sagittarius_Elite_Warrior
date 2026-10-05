"""`EPIC-033D` — the Dev Board's Load history, Start live, Stop live,
Enable live trading, Emergency stop and New order are actions.

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
    LOAD_HISTORY,
    NEW_ORDER,
    START_LIVE,
    STOP_LIVE,
    dev_board_commands,
)
from Sagittarius_Elite_Warrior.tests.command_actions import (
    RecordingConfirmer,
    bound_actions,
)
from Sagittarius_Elite_Warrior.tests.conftest import real_contributions

_ALL = (
    LOAD_HISTORY,
    START_LIVE,
    STOP_LIVE,
    ENABLE_TRADING,
    EMERGENCY_STOP,
    NEW_ORDER,
)


class _Board:
    """A view model, its commands bound, and what they asked for."""

    def __init__(self) -> None:
        self.owner = QObject()
        self.view_model = DashboardQmlViewModel()
        self.confirmer = RecordingConfirmer()
        self.orders_opened = 0
        self.requests: list[str] = []
        self.view_model.loadHistoryRequested.connect(
            lambda: self.requests.append("load")
        )
        self.view_model.startStreamRequested.connect(
            lambda: self.requests.append("start")
        )
        self.view_model.stopStreamRequested.connect(
            lambda: self.requests.append("stop live")
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

    for command_id in _ALL:
        assert modes[command_id] == DASHBOARD_ROUTE


def test_each_action_makes_the_request_its_button_made(qapp) -> None:
    board = _Board()

    for command_id in (LOAD_HISTORY, START_LIVE, ENABLE_TRADING, EMERGENCY_STOP):
        board.registry.action(command_id).trigger()
    board.view_model.set_ui_mode("LIVE")
    board.registry.action(STOP_LIVE).trigger()
    board.registry.action(NEW_ORDER).trigger()

    assert board.requests == ["load", "start", "toggle", "stop", "stop live"]
    assert board.orders_opened == 1
    assert [asked.title for asked in board.confirmer.asked] == ["Emergency stop"]
    assert board.registry.unbound() == ()


def test_load_and_start_follow_the_controls_and_the_running_load(qapp) -> None:
    board = _Board()
    load, start = board.registry.action(LOAD_HISTORY), board.registry.action(START_LIVE)
    assert load.isEnabled() and start.isEnabled()

    board.view_model.set_history_loading(True)
    assert not load.isEnabled() and not start.isEnabled()

    board.view_model.set_history_loading(False)
    board.view_model.set_ui_mode("LIVE")
    assert not load.isEnabled() and not start.isEnabled()


def test_stop_live_applies_while_live_and_while_a_sync_is_locked(qapp) -> None:
    """BOT-123: Start live spends its first phase in LOCKED, syncing from
    Binance before the websocket opens, sometimes for many seconds; Stop
    live is how that sync is cancelled, so it applies in LOCKED as in LIVE."""
    board = _Board()
    stop = board.registry.action(STOP_LIVE)
    assert not stop.isEnabled()

    for mode, applies in (("LOCKED", True), ("LIVE", True), ("IDLE", False)):
        board.view_model.set_ui_mode(mode)
        assert stop.isEnabled() is applies


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


def test_enable_starts_checked_when_trading_was_on_before_the_binding(qapp) -> None:
    view_model = DashboardQmlViewModel()
    view_model.set_trading_state(enabled=True, busy=False)
    owner = QObject()

    registry = bound_actions(
        owner,
        dev_board_commands(DASHBOARD_ROUTE),
        lambda binder: bind_dev_board_commands(binder, view_model, lambda: None),
    )

    assert registry.action(ENABLE_TRADING).isChecked()
