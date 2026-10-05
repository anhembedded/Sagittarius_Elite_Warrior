"""`EPIC-033P` stage 2 — the Developer mode: the event log central, the
probes docked right (HLD §11.2.1), only under developer mode.

The presenter is built on a container whose bus is the Engine's real one; the
recorder it starts is the Engine's process-wide observer, so an emit on any
bus reaches the log once the presenter drains.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QDockWidget, QLabel, QMainWindow
from Sagittarius_Elite_Warrior.src.core.contracts import (
    ContributionDescriptor,
    Place,
    SizeHint,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_table import (
    IContributionTable,
)
from Sagittarius_Elite_Warrior.src.shell.contribution_registry import (
    ContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.shell.developer_mode.bus_event_recorder import (
    BusEventRecord,
    BusEventRecorder,
)
from Sagittarius_Elite_Warrior.src.shell.developer_mode.developer_presenter import (
    DeveloperPresenter,
)
from Sagittarius_Elite_Warrior.src.shell.developer_mode.developer_screen import (
    DEVELOPER_ROUTE,
    developer_screen,
)
from Sagittarius_Elite_Warrior.src.shell.developer_mode.developer_view import (
    EMPTY_LOG_TEXT,
    DeveloperView,
    lost_text,
)
from Sagittarius_Elite_Warrior.src.shell.developer_mode.event_log_table_model import (
    EventLogTableModel,
)
from Sagittarius_Elite_Warrior.src.shell.surfaces import DEV_MODE_GATE
from Sagittarius_Elite_Warrior.tests.conftest import fake_container
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.event_bus.bus_observers import bus_observers
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (
    MemoryEventBus,
)
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_event_bus import IEventBus

_AT = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
_PROBE_TITLE = "A probe"


def _record(event: str, handlers: int | None = 1) -> BusEventRecord:
    return BusEventRecord(_AT, event, handlers)


def _probe(_container: object) -> QLabel:
    return QLabel("probe body")


def _table_with_a_probe() -> ContributionRegistry:
    registry = ContributionRegistry(dev_mode=True)
    registry.contribute(
        ContributionDescriptor(
            contributor_id="probes",
            surface_id="developer",
            place=Place.DEV_PROBE,
            order=10,
            size_hint=SizeHint.REGULAR,
            factory=_probe,
            title=_PROBE_TITLE,
        )
    )
    return registry


@pytest.fixture
def mode(qtbot):
    """A Developer mode on a real bus, probes from a real table."""
    view = DeveloperView()
    qtbot.addWidget(view)
    bus = MemoryEventBus()
    container = fake_container(
        {
            IEventBus: bus,
            IConfig: DictConfig({}),
            IContributionTable: _table_with_a_probe(),
        }
    )
    presenter = DeveloperPresenter(view, container)
    yield view, presenter, bus
    presenter.dispose()


def test_the_mode_is_the_shells_and_exists_only_under_developer_mode() -> None:
    screen = developer_screen()

    assert screen.route == DEVELOPER_ROUTE
    assert screen.contributor_id == "shell"
    assert screen.gated_by == DEV_MODE_GATE
    assert screen.nav is not None
    assert screen.nav.title == "Developer"


def test_the_event_log_is_the_central_widget(qtbot) -> None:
    view = DeveloperView()
    qtbot.addWidget(view)

    host = view.findChild(QMainWindow)
    assert host is not None
    assert host.centralWidget().isAncestorOf(view.event_log.view)


def test_an_empty_log_says_why_it_is_empty(qtbot) -> None:
    view = DeveloperView()
    qtbot.addWidget(view)

    texts = [label.text() for label in view.findChildren(QLabel)]
    assert EMPTY_LOG_TEXT in texts


def test_a_contributed_probe_is_docked_on_the_right(mode) -> None:
    view, _, _ = mode

    docks = {dock.windowTitle(): dock for dock in view.findChildren(QDockWidget)}

    assert _PROBE_TITLE in docks
    host = view.findChild(QMainWindow)
    assert host.dockWidgetArea(docks[_PROBE_TITLE]) == (
        Qt.DockWidgetArea.RightDockWidgetArea
    )


def test_what_the_bus_does_reaches_the_log_on_a_drain(mode) -> None:
    view, presenter, bus = mode
    bus.on("OrderPlaced", lambda _event: None)

    bus.emit("OrderPlaced")
    bus.emit("Nobody listens")
    presenter.drain()

    log = view.event_log
    assert [log.text(row, 1) for row in range(2)] == ["OrderPlaced", "Nobody listens"]
    assert log.text(0, 3) == "delivered to 1 handler"
    assert log.text(1, 3) == "no handler"


def test_a_handler_that_raises_shows_in_the_log(mode) -> None:
    view, presenter, bus = mode

    def broken(_event: object) -> None:
        raise RuntimeError("boom")

    bus.on("Tick", broken)
    bus.emit("Tick")
    presenter.drain()

    outcomes = [view.event_log.text(row, 3) for row in range(2)]
    assert outcomes[0] == "delivered to 1 handler"
    assert outcomes[1].startswith("failed in ")
    assert "RuntimeError: boom" in outcomes[1]


def test_shutting_the_window_down_stops_recording(qtbot) -> None:
    view = DeveloperView()
    qtbot.addWidget(view)
    container = fake_container({IEventBus: MemoryEventBus(), IConfig: DictConfig({})})
    before = set(bus_observers())
    presenter = DeveloperPresenter(view, container)
    assert len(bus_observers()) == len(before) + 1

    presenter.dispose()

    assert set(bus_observers()) == before


def test_a_run_without_a_contribution_table_places_no_probe(qtbot) -> None:
    """A `Mock` container (the smoke tests that build every route) is not a
    table; the mode still builds, with its log and no probe."""
    view = DeveloperView()
    qtbot.addWidget(view)
    container = fake_container({IEventBus: MemoryEventBus(), IConfig: DictConfig({})})

    presenter = DeveloperPresenter(view, container)

    assert view.findChildren(QDockWidget) == []
    presenter.dispose()


def test_a_drain_after_a_burst_says_what_the_log_lost(qtbot) -> None:
    view = DeveloperView()
    qtbot.addWidget(view)
    container = fake_container({IEventBus: MemoryEventBus(), IConfig: DictConfig({})})
    recorder = BusEventRecorder(capacity=1)
    presenter = DeveloperPresenter(view, container, recorder)
    for name in ("A", "B", "C"):
        recorder.event_emitted(name, 0)

    presenter.drain()

    assert view.lost_text == lost_text(2)
    assert view.event_log.text(0, 1) == "C"
    presenter.dispose()


def test_the_log_says_when_it_fell_behind(qtbot) -> None:
    view = DeveloperView()
    qtbot.addWidget(view)
    assert view.lost_text == ""

    view.show_lost(3)

    assert view.lost_text == lost_text(3)
    assert "3 events were not logged" in view.lost_text


def test_the_log_keeps_its_newest_rows_without_a_reset(qtbot) -> None:
    """Row signals, not a reset: the person's selection survives an append."""
    model = EventLogTableModel(limit=3)
    resets: list[bool] = []
    model.modelReset.connect(lambda: resets.append(True))

    model.append([_record("A"), _record("B")])
    model.append([_record("C"), _record("D")])

    assert [row.event for row in model.rows] == ["B", "C", "D"]
    assert resets == []
    assert model.rowCount(QModelIndex()) == 3


def test_a_batch_larger_than_the_log_keeps_its_newest(qtbot) -> None:
    model = EventLogTableModel(limit=2)

    model.append([_record("A"), _record("B"), _record("C")])

    assert [row.event for row in model.rows] == ["B", "C"]
