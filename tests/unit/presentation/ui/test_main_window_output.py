"""`EPIC-033F` — one Output pane, a channel per screen that keeps a log.

Built against a real `ScreenRegistry`, the Engine's real `OutputPane` and real
`LogListModel`s; the views are plain widgets implementing `IOutputSource`,
which is all the window asks of a screen with a log.
"""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QLabel
from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import NavMetadata
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.support.ui_kit.registry import (
    ScreenDescriptor,
    ScreenRegistry,
)
from Sagittarius_Elite_Warrior.tests.unit.presentation.ui.main_window_fakes import (
    DisposeLog,
    PlainPresenter,
    engine,
)
from sagittarius_engine.extensions.pyside_mvc import LogListModel
from sagittarius_engine.extensions.pyside_mvc.workbench.output_pane import (
    OutputChannel,
    OutputPane,
)


class _LoggingView(QLabel):
    def __init__(self, channel_id: str, title: str) -> None:
        super().__init__(title)
        self.lines = LogListModel(self)
        self._channel = OutputChannel(channel_id, title, self.lines)

    def output_channel(self) -> OutputChannel:
        return self._channel


class _ViewWithNoLogThisRun(QLabel):
    def output_channel(self) -> None:
        return None


def _screen(
    route: str, sequence: int, view_factory, log: DisposeLog
) -> ScreenDescriptor:
    return ScreenDescriptor(
        route=route,
        presenter_class=lambda view, container: PlainPresenter(route, log),
        view_factory=view_factory,
        nav=NavMetadata(title=route.title(), icon="circle", item_sequence=sequence),
        is_default=sequence == 1,
    )


def _window(qtbot) -> MainWindow:
    log = DisposeLog()
    registry = ScreenRegistry()
    registry.register(_screen("desk", 1, lambda: _LoggingView("desk.log", "Desk"), log))
    registry.register(_screen("chart", 2, lambda: QLabel("no log"), log))
    registry.register(_screen("idle", 4, lambda: _ViewWithNoLogThisRun("idle"), log))
    registry.register(
        _screen("data", 3, lambda: _LoggingView("data.sync", "Sync"), log)
    )
    window = MainWindow(engine(), registry)
    qtbot.addWidget(window)
    return window


def _pane(window: MainWindow) -> OutputPane:
    pane = window.findChild(OutputPane, "workbench::output")
    assert pane is not None
    return pane


def _channel_titles(pane: OutputPane) -> list[str]:
    choice = pane.findChild(QComboBox, "workbench::output::channel")
    assert choice is not None
    return [choice.itemText(index) for index in range(choice.count())]


def test_each_screen_with_a_log_is_one_channel_in_mode_order(qtbot) -> None:
    pane = _pane(_window(qtbot))

    assert _channel_titles(pane) == ["Desk", "Sync"]


def test_showing_a_mode_brings_its_channel_forward(qtbot) -> None:
    window = _window(qtbot)
    pane = _pane(window)

    window.switch_screen("data")

    current = pane.current_channel
    assert current is not None
    assert current.channel_id == "data.sync"


def test_a_mode_without_a_log_leaves_the_channel_showing(qtbot) -> None:
    window = _window(qtbot)
    pane = _pane(window)
    window.switch_screen("data")

    window.switch_screen("chart")

    current = pane.current_channel
    assert current is not None
    assert current.channel_id == "data.sync"


def test_a_screens_lines_reach_the_pane(qtbot) -> None:
    window = _window(qtbot)
    pane = _pane(window)
    view = window.hosts["desk"].findChild(_LoggingView)
    assert view is not None

    view.lines.append("order sent")

    assert pane.copy_lines().endswith("order sent")
