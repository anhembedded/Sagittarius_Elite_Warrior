"""`TimezonePickerVM` — the widget's rules, tested with no GUI at all.

Deliberately does NOT use the `qapp` fixture. A widget ViewModel is a plain
`QObject`: `Property`, `Signal` and `Slot` all work with no `QApplication`
and no event loop, which is what makes this tier fast and non-flaky. Measured
standalone in `Tasks/epics/EPIC-015.../spike/vm_alone.py`, where
`QApplication.instance()` is `None` for the whole run.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TimezonePicker.timezone_picker_vm import (
    TimezonePickerVM,
)

_OPTIONS = [
    {"id": "UTC", "label": "UTC (Giờ phối hợp quốc tế)"},
    {"id": "Asia/Tokyo", "label": "Tokyo"},
]


def _vm(current="UTC", options=None):
    return TimezonePickerVM(
        get_options=lambda: _OPTIONS if options is None else options,
        get_current=lambda: current,
    )


def test_rows_are_empty_until_refreshed():
    """Nothing is read at construction — the dialog is built once and reused,
    so every value has to come from the open, not from the build."""
    assert _vm().rows == []


def test_refresh_marks_exactly_the_current_timezone():
    """`selected` is computed here, not in the Repeater delegate. A delegate
    asking "am I the current one?" is a rule living where no test can reach."""
    vm = _vm(current="Asia/Tokyo")
    vm.refresh()

    assert [r["selected"] for r in vm.rows] == [False, True]


def test_a_current_timezone_that_is_no_longer_offered_selects_nothing():
    """Better than guessing a row: the footer still says what is in use, and
    no wrong row is highlighted."""
    vm = _vm(current="Mars/Olympus")
    vm.refresh()

    assert not any(r["selected"] for r in vm.rows)


def test_an_option_with_no_label_falls_back_to_its_id():
    """Rows come from the screen's ViewModel and ultimately from config —
    a blank label must not render a blank, unclickable-looking row."""
    vm = _vm(options=[{"id": "UTC"}])
    vm.refresh()

    assert vm.rows[0]["label"] == "UTC"


def test_reopening_re_reads_the_current_timezone():
    current = {"value": "UTC"}
    vm = TimezonePickerVM(lambda: _OPTIONS, lambda: current["value"])
    vm.refresh()
    assert vm.rows[0]["selected"] is True

    current["value"] = "Asia/Tokyo"
    vm.refresh()

    assert [r["selected"] for r in vm.rows] == [False, True]


def test_choosing_emits_rather_than_writing_through():
    """The widget has no opinion about which screen owns it."""
    vm = _vm()
    chosen: list[str] = []
    vm.chosen.connect(chosen.append)

    vm.choose("Asia/Tokyo")

    assert chosen == ["Asia/Tokyo"]


def test_choosing_nothing_is_ignored():
    vm = _vm()
    chosen: list[str] = []
    vm.chosen.connect(chosen.append)

    vm.choose("")

    assert chosen == []


def test_refresh_announces_the_change():
    """The QML `Repeater` re-reads `rows` on this signal; without it the list
    renders once and never updates."""
    vm = _vm()
    fired: list[int] = []
    vm.optionsChanged.connect(lambda: fired.append(1))

    vm.refresh()

    assert fired == [1]
