"""`EPIC-033D` — a contributed command is one `QAction` in the window.

Built against a real `ScreenRegistry` and the Engine's real `ActionRegistry`;
the presenters are doubles that implement what the window calls on them,
`dispose()` and, for the one that performs commands, a real
`CommandPresenter`'s `bind_commands()`.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLabel, QToolBar, QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandContribution,
)
from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import NavMetadata
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_presenter import (
    CommandPresenter,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.registry import (
    ScreenDescriptor,
    ScreenRegistry,
)
from Sagittarius_Elite_Warrior.tests.conftest import fake_container
from Sagittarius_Elite_Warrior.tests.unit.presentation.ui.main_window_fakes import (
    DisposeLog,
    PlainPresenter,
    engine,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (
    MemoryEventBus,
)
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_event_bus import IEventBus

_ENABLE = CommandContribution(
    contributor_id="trading",
    command_id="desk.enable",
    text="&Enable live trading",
    menu_path=("T&rade",),
    mode="desk",
    on_toolbar=True,
    checkable=True,
)
_STOP = CommandContribution(
    contributor_id="trading",
    command_id="trading.emergency_stop",
    text="Emergency &stop",
    menu_path=("T&rade",),
    on_toolbar=True,
    shortcut="F8",
)
_SYNC = CommandContribution(
    contributor_id="market_data",
    command_id="data.sync",
    text="&Sync history…",
    menu_path=("&Data",),
    mode="data",
    needs_input=True,
)


class _DeskPresenter(CommandPresenter):
    """Performs `desk.enable` and `trading.emergency_stop`. A real
    `CommandPresenter` (the window binds only those), over a fake container
    whose bus and config are the Engine's in-memory ones."""

    class _State(QObject):
        ready = Signal(bool)

    def __init__(self, view: QWidget, log: DisposeLog) -> None:
        super().__init__(
            view,
            fake_container({IEventBus: MemoryEventBus(), IConfig: DictConfig({})}),
        )
        self._log = log
        self.state = self._State()
        self.toggled: list[bool] = []
        self.stopped = 0

    def bind_commands(self, binder: ICommandBinder) -> None:
        binder.bind(
            "desk.enable",
            self.toggled.append,
            enabled=self.state.ready,
            initially_enabled=False,
        )
        binder.bind("trading.emergency_stop", self._stop)

    def dispose(self) -> None:
        self._log.routes.append("desk")
        super().dispose()

    def _stop(self, _checked: bool) -> None:
        self.stopped += 1


def _registry(log: DisposeLog, desks: list[_DeskPresenter]) -> ScreenRegistry:
    def desk(view, container) -> _DeskPresenter:
        presenter = _DeskPresenter(view, log)
        desks.append(presenter)
        return presenter

    registry = ScreenRegistry()
    registry.register(
        ScreenDescriptor(
            route="desk",
            presenter_class=desk,
            view_factory=lambda: QLabel("desk"),
            nav=NavMetadata(title="Desk", icon="circle", item_sequence=1),
            is_default=True,
        )
    )
    registry.register(
        ScreenDescriptor(
            route="data",
            presenter_class=lambda view, container: PlainPresenter("data", log),
            view_factory=lambda: QLabel("data"),
            nav=NavMetadata(title="Data", icon="circle", item_sequence=2),
        )
    )
    for command in (_ENABLE, _STOP, _SYNC):
        registry.register_command(command)
    return registry


def _window(qtbot, desks: list[_DeskPresenter]) -> MainWindow:
    window = MainWindow(engine(), _registry(DisposeLog(), desks))
    qtbot.addWidget(window)
    return window


def _action(window: MainWindow, command_id: str) -> QAction:
    action = window.findChild(QAction, f"action::{command_id}")
    assert action is not None
    return action


def _toolbar_actions(window: MainWindow, mode: str) -> list[QAction]:
    bar = window.hosts[mode].findChild(QToolBar)
    return [] if bar is None else bar.actions()


def test_a_command_is_in_its_menu_for_its_mode(qtbot) -> None:
    window = _window(qtbot, [])

    texts = [action.text() for action in window.menu("T&rade").actions()]

    assert "&Enable live trading" in texts
    assert "Emergency &stop" in texts


def test_a_toolbar_command_is_on_its_modes_toolbar_and_an_all_modes_one_on_each(
    qtbot,
) -> None:
    window = _window(qtbot, [])
    enable, stop = (
        _action(window, "desk.enable"),
        _action(window, "trading.emergency_stop"),
    )

    assert _toolbar_actions(window, "desk") == [enable, stop]
    assert _toolbar_actions(window, "data") == [stop]


def test_triggering_the_action_runs_the_presenters_handler(qtbot) -> None:
    desks: list[_DeskPresenter] = []
    window = _window(qtbot, desks)
    enable = _action(window, "desk.enable")
    desks[0].state.ready.emit(True)

    enable.trigger()

    assert desks[0].toggled == [True]


def test_the_presenter_decides_when_its_command_is_enabled(qtbot) -> None:
    desks: list[_DeskPresenter] = []
    window = _window(qtbot, desks)
    enable = _action(window, "desk.enable")
    assert not enable.isEnabled()

    desks[0].state.ready.emit(True)
    assert enable.isEnabled()

    desks[0].state.ready.emit(False)
    assert not enable.isEnabled()


def test_a_command_nothing_performs_stays_disabled(qtbot) -> None:
    window = _window(qtbot, [])

    assert not _action(window, "data.sync").isEnabled()


def test_a_presenter_that_only_looks_like_one_is_not_bound(qtbot) -> None:
    """The window binds a `CommandPresenter`, not anything with the method."""

    class _LookAlike(PlainPresenter):
        def bind_commands(self, binder: ICommandBinder) -> None:
            raise AssertionError("bound a presenter that is not a CommandPresenter")

    registry = ScreenRegistry()
    registry.register(
        ScreenDescriptor(
            route="desk",
            presenter_class=lambda view, container: _LookAlike("desk", DisposeLog()),
            view_factory=lambda: QLabel("desk"),
            nav=NavMetadata(title="Desk", icon="circle", item_sequence=1),
            is_default=True,
        )
    )
    registry.register_command(_ENABLE)

    window = MainWindow(engine(), registry)
    qtbot.addWidget(window)

    assert not _action(window, "desk.enable").isEnabled()
