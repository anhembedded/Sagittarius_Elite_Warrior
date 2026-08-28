"""`CheckboxListVM` — no GUI.

Deliberately does NOT test the `order_execution_dialog`'s mutual-exclusion
rule here — that rule lives in the dialog, not this VM (`EPIC-015` §4c,
`CheckboxList/NOTES.md`). This VM only has to prove it renders whatever it is
handed and reports raw toggles.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.qml.CheckboxList.checkbox_list_vm import (
    CheckboxListVM,
)


def test_rows_are_empty_until_refreshed():
    vm = CheckboxListVM(get_rows=lambda: [{"key": "a", "label": "A"}])
    assert vm.rows == []


def test_a_row_defaults_unchecked_and_unlocked():
    vm = CheckboxListVM(get_rows=lambda: [{"key": "a", "label": "A"}])
    vm.refresh()

    assert vm.rows == [
        {"key": "a", "label": "A", "checked": False, "locked": False, "tooltip": ""}
    ]


def test_toggling_emits_the_raw_key_and_state():
    """The VM does not write anything back — the screen decides."""
    vm = CheckboxListVM(get_rows=list)
    seen: list[tuple[str, bool]] = []
    vm.toggled.connect(lambda key, checked: seen.append((key, checked)))

    vm.toggle("scriptA", True)
    vm.toggle("scriptA", False)

    assert seen == [("scriptA", True), ("scriptA", False)]


def test_refresh_announces_the_change():
    vm = CheckboxListVM(get_rows=list)
    fired: list[int] = []
    vm.rowsChanged.connect(lambda: fired.append(1))

    vm.refresh()

    assert fired == [1]


def test_a_locked_row_keeps_its_flag():
    vm = CheckboxListVM(
        get_rows=lambda: [{"key": "a", "label": "A", "locked": True, "checked": True}]
    )
    vm.refresh()

    assert vm.rows[0]["locked"] is True
    assert vm.rows[0]["checked"] is True
