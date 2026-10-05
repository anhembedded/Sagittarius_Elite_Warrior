"""The Data mode's view (`EPIC-033J`): HLD §11.2.1's layout, the status
bar's words, and a selected shard becoming what the commands act on."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QMainWindow
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_view import (
    DATA_SURFACE,
    DataManagementView,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_view_model import (
    DataManagementViewModel,
)
from Sagittarius_Elite_Warrior.src.shell.surfaces import surfaces_by_id
from Sagittarius_Elite_Warrior.src.support.ui_kit.status_source import IStatusSource

_AT = datetime(2026, 10, 1, tzinfo=UTC)


@pytest.fixture
def mode(qapp):
    view_model = DataManagementViewModel()
    view = DataManagementView()
    view.set_view_model(view_model)
    yield view_model, view
    view.deleteLater()


def test_the_view_renders_the_surface_the_shell_declares() -> None:
    assert surfaces_by_id()["data_management"] == DATA_SURFACE


def test_the_coverage_table_is_central_and_the_gaps_are_docked_below(mode):
    _view_model, view = mode
    surface = view.findChild(QMainWindow)
    docks = view.findChildren(QDockWidget)

    assert surface.centralWidget().isAncestorOf(view.status_panel)
    assert [dock.windowTitle() for dock in docks] == ["Gaps"]
    assert surface.dockWidgetArea(docks[0]) is Qt.DockWidgetArea.BottomDockWidgetArea


def test_records_and_size_are_words_in_the_status_bar(mode):
    view_model, view = mode

    view_model.set_stats("1,250", "3.2 MB")

    assert isinstance(view, IStatusSource)
    texts = [widget.text() for widget in view.status_widgets()[:2]]
    assert texts == ["Records: 1,250", "Database: 3.2 MB"]


def test_selecting_a_shard_is_recorded_in_the_selection(mode):
    """The selection is the one record of what the commands act on; the
    view model's symbol is written only when a command acts (review of
    PR #354)."""
    view_model, view = mode
    before = (view_model.selectedSymbol, view_model.selectedInterval)
    view_model.status_model.upsert_row("ETHUSDT", _AT, _AT, 10, "OK", "4h")
    seen: list[object] = []
    view.selection.changed.connect(lambda: seen.append(view.selection.shard))

    view.status_panel._table.selectRow(0)

    assert seen[-1] is not None
    assert (seen[-1].symbol, seen[-1].interval) == ("ETHUSDT", "4h")
    assert (view_model.selectedSymbol, view_model.selectedInterval) == before


def test_a_gap_answer_raises_the_gaps_panel_and_marks_gaps_listed(mode):
    view_model, view = mode
    view.resize(1024, 700)
    view.show()
    view.gaps_dock.hide()

    view_model.set_gap_inspector_data(
        "ETHUSDT",
        "4h",
        1,
        12,
        97.0,
        [{"gap_id": 1, "start_time": "a", "end_time": "b", "missing_candles": 12}],
        [],
    )

    assert view.gaps_dock.isVisible()
    assert view.selection.gaps_listed is True
