"""No-GUI tests for TimeframeVM."""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.components.timeframe_picker import (
    GROUP_CAPTIONS,
    GROUP_LABELS,
    all_options,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TimeframePicker.timeframe_vm import (
    TimeframeVM,
)

_ALL_CODES = [option.code for option in all_options()]


def _vm(
    *,
    codes: list[str] | None = None,
    current: str = "1m",
    pinned: tuple[str, ...] = ("1m", "5m", "15m", "1h", "1d"),
) -> tuple[TimeframeVM, dict[str, object]]:
    state = {"current": current, "pinned": set(pinned), "set_calls": []}
    vm = TimeframeVM(
        get_codes=lambda: codes if codes is not None else _ALL_CODES,
        get_current=lambda: state["current"],
        get_pinned=lambda: state["pinned"],
        set_pinned=lambda code, pin: state["set_calls"].append((code, pin)),
    )
    vm.refresh()
    return vm, state


def test_refresh_builds_pinned_rows_in_catalogue_order():
    vm, _ = _vm(pinned=("1h", "1m", "1d"))  # deliberately out of order

    assert [row["code"] for row in vm.pinnedRows] == ["1m", "1h", "1d"]
    assert vm.pinnedRows[0]["current"] is True


def test_refresh_builds_groups_with_labels_and_captions():
    vm, _ = _vm()

    assert [group["label"] for group in vm.groups] == list(GROUP_LABELS.values())
    assert [group["caption"] for group in vm.groups] == list(GROUP_CAPTIONS.values())
    minutes_group = next(g for g in vm.groups if g["label"] == "PHÚT")
    assert [row["code"] for row in minutes_group["rows"]] == [
        "1m",
        "3m",
        "5m",
        "15m",
        "30m",
    ]


def test_seconds_group_has_exactly_one_card_today():
    """The mockup shows 1s/5s/15s/30s; the domain (and Binance) only has 1s
    — see NOTES.md. This pins down that the VM renders reality, not the
    mockup's aspirational count, so a future domain change is what should
    make this test fail, not a VM bug."""
    vm, _ = _vm()

    seconds_group = next(g for g in vm.groups if g["label"] == "GIÂY")
    assert [row["code"] for row in seconds_group["rows"]] == ["1s"]


def test_has_warning_only_when_the_second_timeframe_is_offered():
    with_seconds, _ = _vm()
    assert with_seconds.hasWarning is True

    without_seconds, _ = _vm(codes=[c for c in _ALL_CODES if c != "1s"])
    assert without_seconds.hasWarning is False


def test_choose_updates_current_and_emits_for_an_offered_code():
    vm, _ = _vm()
    chosen: list[str] = []
    vm.chosen.connect(chosen.append)

    vm.choose("15m")

    assert vm.currentCode == "15m"
    assert chosen == ["15m"]
    assert next(row for row in vm.pinnedRows if row["code"] == "15m")["current"] is True


def test_choose_ignores_an_unoffered_code():
    vm, _ = _vm(codes=["1m", "1h"])
    chosen: list[str] = []
    vm.chosen.connect(chosen.append)

    vm.choose("5m")

    assert vm.currentCode == "1m"
    assert chosen == []


def test_toggle_pinned_adds_removes_and_writes_through_to_the_host():
    vm, state = _vm(pinned=())

    vm.togglePinned("1m")
    assert state["set_calls"] == [("1m", True)]
    assert [row["code"] for row in vm.pinnedRows] == ["1m"]

    vm.togglePinned("1m")
    assert state["set_calls"] == [("1m", True), ("1m", False)]
    assert vm.pinnedRows == []


def test_set_current_updates_the_highlight_without_emitting():
    """`ChartToolbar.set_active()`'s contract: sync the highlight, do not
    trigger the same handler that called it in the first place."""
    vm, _ = _vm()
    chosen: list[str] = []
    vm.chosen.connect(chosen.append)

    vm.set_current("15m")

    assert vm.currentCode == "15m"
    assert chosen == []
    assert next(row for row in vm.pinnedRows if row["code"] == "15m")["current"] is True


def test_set_current_accepts_a_code_outside_the_offered_set():
    """Unlike `choose()`, no membership gate — matches the old widget's
    behaviour of still reporting a stale/unlisted config value rather than
    silently keeping the previous one."""
    vm, _ = _vm(codes=["1m", "1h"])

    vm.set_current("4h")

    assert vm.currentCode == "4h"
    assert all(row["current"] is False for row in vm.pinnedRows)


def test_set_current_with_none_reports_an_empty_current_code():
    vm, _ = _vm()

    vm.set_current(None)

    assert vm.currentCode == ""


def test_toggle_pinned_ignores_an_unoffered_code():
    vm, state = _vm(codes=["1m"], pinned=())

    vm.togglePinned("5m")

    assert state["set_calls"] == []
    assert vm.pinnedRows == []


def test_pinning_is_reflected_in_the_groups_view_too():
    """The whole reason for one VM instead of two: a toggle from the picker
    must be visible to the toolbar-shaped view without a second refresh."""
    vm, _ = _vm(pinned=())

    vm.togglePinned("4h")

    hours_group = next(g for g in vm.groups if g["label"] == "GIỜ")
    row = next(r for r in hours_group["rows"] if r["code"] == "4h")
    assert row["pinned"] is True
    assert any(pin["code"] == "4h" for pin in vm.pinnedRows)
