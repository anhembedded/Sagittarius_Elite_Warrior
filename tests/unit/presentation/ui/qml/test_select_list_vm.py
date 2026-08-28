"""`SelectListVM` — no GUI. Generalised from `TimezonePickerVM` after counting
the remaining modals turned up two more consumers of the exact same shape
(`EPIC-015` §4c)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.qml.SelectList.select_list_vm import (
    SelectListVM,
)

_OPTIONS = [
    {"id": "UTC", "label": "UTC (Giờ phối hợp quốc tế)"},
    {"id": "Asia/Tokyo", "label": "Tokyo"},
]


def _selectable_vm(current="UTC", options=None):
    return SelectListVM(
        get_options=lambda: _OPTIONS if options is None else options,
        get_current=lambda: current,
    )


def test_rows_are_empty_until_refreshed():
    assert _selectable_vm().rows == []


def test_refresh_marks_exactly_the_current_option():
    vm = _selectable_vm(current="Asia/Tokyo")
    vm.refresh()

    assert [r["selected"] for r in vm.rows] == [False, True]


def test_a_current_value_no_longer_offered_selects_nothing():
    vm = _selectable_vm(current="Mars/Olympus")
    vm.refresh()

    assert not any(r["selected"] for r in vm.rows)


def test_an_option_with_no_label_falls_back_to_its_id():
    vm = _selectable_vm(options=[{"id": "UTC"}])
    vm.refresh()

    assert vm.rows[0]["label"] == "UTC"


def test_a_subtitle_defaults_to_empty():
    vm = _selectable_vm(options=[{"id": "UTC", "label": "UTC"}])
    vm.refresh()

    assert vm.rows[0]["subtitle"] == ""


def test_a_supplied_subtitle_is_kept():
    vm = SelectListVM(
        get_options=lambda: [{"id": "k", "label": "Chiến lược K", "subtitle": "Mã: k"}]
    )
    vm.refresh()

    assert vm.rows[0]["subtitle"] == "Mã: k"


def test_choosing_emits_rather_than_writing_through():
    vm = _selectable_vm()
    chosen: list[str] = []
    vm.chosen.connect(chosen.append)

    vm.choose("Asia/Tokyo")

    assert chosen == ["Asia/Tokyo"]


def test_choosing_nothing_is_ignored():
    vm = _selectable_vm()
    chosen: list[str] = []
    vm.chosen.connect(chosen.append)

    vm.choose("")

    assert chosen == []


# -- selectable=False: the read-only bullet-list shape ---------------------- #


def test_a_readonly_list_needs_no_current_getter():
    """`limitations_dialog` has no "currently selected" concept at all."""
    vm = SelectListVM(get_options=lambda: [{"id": "0", "label": "x"}], selectable=False)
    vm.refresh()

    assert vm.rows[0]["selected"] is False


def test_a_readonly_list_never_marks_anything_selected():
    vm = SelectListVM(
        get_options=lambda: _OPTIONS,
        get_current=lambda: "UTC",
        selectable=False,
    )
    vm.refresh()

    assert not any(r["selected"] for r in vm.rows)


def test_choosing_on_a_readonly_list_does_nothing():
    vm = SelectListVM(get_options=lambda: _OPTIONS, selectable=False)
    chosen: list[str] = []
    vm.chosen.connect(chosen.append)

    vm.choose("UTC")

    assert chosen == []


def test_selectable_flag_is_exposed_as_a_constant_property():
    assert _selectable_vm().selectable is True
    assert SelectListVM(get_options=list, selectable=False).selectable is False
