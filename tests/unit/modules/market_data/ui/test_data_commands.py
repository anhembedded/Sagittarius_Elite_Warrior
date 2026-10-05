"""`EPIC-033D`/`033J` — the Data mode's commands are actions that act on what
is selected and apply while no task runs.

The commands the market-data module really contributes, bound over a real
view model and a real view; the two dialogs are answered by the test.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_command_binding import (
    bind_data_commands,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_commands import (
    CHECK_GAPS,
    DELETE_SELECTED,
    EXPORT,
    IMPORT,
    INSPECT_CANDLES,
    OPTIMIZE,
    PURGE_ALL,
    REPAIR_ALL_GAPS,
    REPAIR_GAP,
    SCAN_ALL,
    SCAN_STATUS,
    STOP,
    SYNC_ALL_GAPS,
    SYNC_HISTORY,
    data_commands,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_view import (
    DataManagementView,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_view_model import (
    DataManagementViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_widgets.shard_dialogs import (
    ShardChoice,
    SyncChoice,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.database_screen import (
    DATABASE_ROUTE,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions
from Sagittarius_Elite_Warrior.tests.conftest import real_contributions

_AT = datetime(2026, 10, 1, tzinfo=UTC)
#: The commands that need nothing selected, and the request each makes.
_FREE = {
    SCAN_ALL: "checkAllStatusRequested",
    SYNC_ALL_GAPS: "syncAllGapsRequested",
    OPTIMIZE: "vacuumRequested",
    PURGE_ALL: "purgeAllRequested",
}
#: The commands that act on the selected shard.
_ON_SHARD = {
    SCAN_STATUS: "checkStatusRequested",
    EXPORT: "exportRequested",
    DELETE_SELECTED: "clearDataRequested",
    INSPECT_CANDLES: "inspectKlinesRequested",
}
_GAP = {
    "gap_id": 1,
    "start_time": "2026-10-01 00:00",
    "end_time": "2026-10-01 01:00",
    "fetch_start_time": "2026-09-30 23:59",
    "fetch_end_time": "2026-10-01 01:01",
    "duration_text": "1h",
    "missing_candles": 60,
}


@pytest.fixture
def mode(qapp):
    view_model = DataManagementViewModel()
    view = DataManagementView()
    view.set_view_model(view_model)
    actions = bound_actions(
        view_model,
        data_commands(DATABASE_ROUTE),
        lambda binder: bind_data_commands(binder, view_model, view),
    )
    yield view_model, view, actions
    view.deleteLater()


def _heard(signal) -> list[tuple]:
    heard: list[tuple] = []
    signal.connect(lambda *args: heard.append(args))
    return heard


def _select(view_model, view, status: str = "3 gaps found") -> None:
    view_model.status_model.upsert_row("ETHUSDT", _AT, _AT, 120, status, "1h")
    view.status_panel._table.selectRow(0)


def test_the_market_data_module_contributes_every_data_command() -> None:
    modes = {
        command.command_id: command.mode
        for command in real_contributions(Mock()).commands()
    }

    for command in data_commands(DATABASE_ROUTE):
        assert modes[command.command_id] == DATABASE_ROUTE


@pytest.mark.parametrize(("command_id", "signal_name"), _FREE.items())
def test_a_command_on_the_whole_store_makes_its_request(
    mode, command_id, signal_name
) -> None:
    view_model, _view, actions = mode
    heard = _heard(getattr(view_model, signal_name))

    actions.action(command_id).trigger()

    assert len(heard) == 1


@pytest.mark.parametrize(("command_id", "signal_name"), _ON_SHARD.items())
def test_a_shard_command_acts_on_the_selected_row_and_waits_for_one(
    mode, command_id, signal_name
) -> None:
    view_model, view, actions = mode
    assert not actions.action(command_id).isEnabled()
    heard = _heard(getattr(view_model, signal_name))

    _select(view_model, view)
    actions.action(command_id).trigger()

    assert len(heard) == 1
    assert (view_model.selectedSymbol, view_model.selectedInterval) == (
        "ETHUSDT",
        "1h",
    )


def test_check_gaps_applies_to_a_shard_with_gaps_only(mode) -> None:
    view_model, view, actions = mode
    heard = _heard(view_model.inspectGapsRequested)

    _select(view_model, view, status="OK")
    assert not actions.action(CHECK_GAPS).isEnabled()
    view_model.status_model.upsert_row("ETHUSDT", _AT, _AT, 120, "3 gaps found", "1h")
    actions.action(CHECK_GAPS).trigger()

    assert heard == [("ETHUSDT", "1h")]


def test_repair_acts_on_the_selected_gap_with_its_fetch_range(mode) -> None:
    view_model, view, actions = mode
    heard = _heard(view_model.repairGapRequested)
    view_model.set_gap_inspector_data("ETHUSDT", "1h", 1, 60, 99.0, [_GAP], [])
    assert not actions.action(REPAIR_GAP).isEnabled()
    assert actions.action(REPAIR_ALL_GAPS).isEnabled()

    view.gaps.select_row(0)
    actions.action(REPAIR_GAP).trigger()

    assert heard == [("ETHUSDT", "1h", "2026-09-30 23:59", "2026-10-01 01:01")]


def test_sync_history_asks_then_syncs_what_was_chosen(mode, monkeypatch) -> None:
    view_model, view, actions = mode
    heard = _heard(view_model.syncRequested)
    asked: list[ShardChoice] = []

    def answer(_symbols, _intervals, current: ShardChoice) -> SyncChoice:
        asked.append(current)
        return SyncChoice(
            ShardChoice("SOLUSDT", "15m"), "2026-09-01 00:00", "2026-09-02 00:00"
        )

    monkeypatch.setattr(view, "ask_sync_history", answer)
    _select(view_model, view)
    actions.action(SYNC_HISTORY).trigger()

    assert asked == [ShardChoice("ETHUSDT", "1h")]
    assert len(heard) == 1
    assert (view_model.selectedSymbol, view_model.selectedInterval) == (
        "SOLUSDT",
        "15m",
    )
    assert view_model.useCustomTime is True
    assert (view_model.fromDateTime, view_model.toDateTime) == (
        "2026-09-01 00:00",
        "2026-09-02 00:00",
    )


def test_a_cancelled_question_does_nothing(mode, monkeypatch) -> None:
    view_model, view, actions = mode
    synced = _heard(view_model.syncRequested)
    imported = _heard(view_model.importRequested)
    monkeypatch.setattr(view, "ask_sync_history", lambda *_args: None)
    monkeypatch.setattr(view, "ask_import_shard", lambda *_args: None)

    actions.action(SYNC_HISTORY).trigger()
    actions.action(IMPORT).trigger()

    assert synced == []
    assert imported == []


def test_import_asks_which_shard_the_file_belongs_to(mode, monkeypatch) -> None:
    view_model, view, actions = mode
    heard = _heard(view_model.importRequested)
    monkeypatch.setattr(
        view, "ask_import_shard", lambda *_args: ShardChoice("ADAUSDT", "4h")
    )

    actions.action(IMPORT).trigger()

    assert len(heard) == 1
    assert (view_model.selectedSymbol, view_model.selectedInterval) == (
        "ADAUSDT",
        "4h",
    )


def test_a_running_task_disables_every_command_but_stop(mode) -> None:
    view_model, view, actions = mode
    _select(view_model, view)
    commands = [command.command_id for command in data_commands(DATABASE_ROUTE)]
    assert not actions.action(STOP).isEnabled()
    heard = _heard(view_model.cancelRequested)

    view_model.set_ui_mode("SYNCING")
    enabled = [c for c in commands if actions.action(c).isEnabled()]
    actions.action(STOP).trigger()

    assert enabled == [STOP]
    assert len(heard) == 1
    view_model.set_ui_mode("IDLE")
    assert not actions.action(STOP).isEnabled()
    assert actions.action(SCAN_STATUS).isEnabled()


def test_the_table_context_menu_repeats_the_shard_commands(mode) -> None:
    _view_model, view, _actions = mode
    table = view.status_panel._table

    assert table.contextMenuPolicy() is Qt.ContextMenuPolicy.ActionsContextMenu
    assert [action.text() for action in table.actions()] == [
        "&Check gaps",
        "&Inspect candles",
        "&Delete data",
    ]
