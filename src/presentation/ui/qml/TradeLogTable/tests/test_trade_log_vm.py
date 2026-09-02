"""No-GUI tests for TradeLogVM."""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101, PLR2004

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TradeLogTable.trade_log_row import (
    TradeLogRow,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TradeLogTable.trade_log_vm import (
    TradeLogVM,
)

_T0 = datetime(2026, 7, 23, 16, 59, tzinfo=UTC)


def _row(index: int, side: PositionSide, pnl: float) -> TradeLogRow:
    return TradeLogRow(
        index=index,
        entry_time=_T0 + timedelta(minutes=index),
        entry_price=100.0,
        exit_time=_T0 + timedelta(minutes=index + 10),
        exit_price=100.0 + pnl,
        quantity=1.0,
        pnl=pnl,
        pnl_percent=pnl,
        side=side,
    )


#: 6 total, 4 long, 2 short, 2 wins, 4 losses — same counts as the mockup.
_ROWS = (
    _row(1, PositionSide.LONG, -1.0),
    _row(2, PositionSide.LONG, -1.0),
    _row(3, PositionSide.LONG, 1.0),
    _row(4, PositionSide.LONG, -1.0),
    _row(5, PositionSide.SHORT, 1.0),
    _row(6, PositionSide.SHORT, -1.0),
)


def _vm(rows=_ROWS) -> TradeLogVM:
    vm = TradeLogVM(get_rows=lambda: rows, get_timezone_name=lambda: "UTC")
    vm.refresh()
    return vm


def test_refresh_shows_every_row_unfiltered_by_default():
    vm = _vm()

    assert len(vm.rows) == 6
    assert vm.totalCount == 6


def test_filter_tab_counts_match_the_mockup():
    vm = _vm()

    counts = {tab["id"]: tab["count"] for tab in vm.filterTabs}
    assert counts == {"all": 6, "long": 4, "short": 2, "win": 2, "loss": 4}


def test_all_tab_is_selected_by_default():
    vm = _vm()

    assert [tab["id"] for tab in vm.filterTabs if tab["selected"]] == ["all"]


def test_choosing_a_filter_narrows_the_visible_rows_and_updates_selection():
    vm = _vm()

    vm.chooseFilter("short")

    assert [row["index"] for row in vm.rows] == ["5", "6"]
    assert [tab["id"] for tab in vm.filterTabs if tab["selected"]] == ["short"]
    # Counts stay the same regardless of which tab is active — they always
    # describe the full set, not the currently-filtered one.
    counts = {tab["id"]: tab["count"] for tab in vm.filterTabs}
    assert counts == {"all": 6, "long": 4, "short": 2, "win": 2, "loss": 4}


def test_an_unknown_filter_id_is_ignored():
    vm = _vm()
    vm.chooseFilter("short")

    vm.chooseFilter("does-not-exist")

    assert [row["index"] for row in vm.rows] == ["5", "6"]


def test_rows_carry_the_side_badge_fields():
    vm = _vm()
    vm.chooseFilter("long")

    assert all(row["sideLabel"] == "LONG" for row in vm.rows)
    assert all(row["sideIsLong"] is True for row in vm.rows)


def test_rows_are_formatted_with_the_injected_timezone():
    vm = TradeLogVM(get_rows=lambda: _ROWS[:1], get_timezone_name=lambda: "UTC")
    vm.refresh()

    assert vm.rows[0]["entryTimeText"] != ""


def test_rows_start_collapsed():
    vm = _vm()

    assert all(row["expanded"] is False for row in vm.rows)


def test_toggle_expanded_flips_only_the_chosen_row():
    vm = _vm()

    vm.toggleExpanded(3)

    expanded = {row["index"] for row in vm.rows if row["expanded"]}
    assert expanded == {"3"}

    vm.toggleExpanded(3)
    assert not any(row["expanded"] for row in vm.rows)


def test_expanded_state_survives_a_filter_change():
    """A row's expanded state is keyed by its stable trade index, not its
    position in the currently-visible list — switching tabs and back must
    not silently collapse it."""
    vm = _vm()
    vm.toggleExpanded(5)  # a SHORT trade

    vm.chooseFilter("short")
    row = next(r for r in vm.rows if r["index"] == "5")
    assert row["expanded"] is True

    vm.chooseFilter("all")
    row = next(r for r in vm.rows if r["index"] == "5")
    assert row["expanded"] is True
