"""`EPIC-015`: `TimeRangePicker.qml`'s host, rendered for real.

Thin on purpose (`qml-rule.md` §7): `TimeRangePickerVM`'s own rules already
have full coverage with no `QApplication` at all
(`qml/TimeRangePicker/tests/test_time_range_picker_vm.py`), and the
standalone `.qml`'s render/interaction behaviour is already covered with no
host at all (`qml/TimeRangePicker/tests/test_time_range_picker_qml.py`).
What only a test building the real `TimeRangePickerDialog`/
`TimeRangePickerDialogWidget` can prove is this app's own wiring: the
footer buttons track `canApply`, `applied` closes the dialog, and Backtest's
composition root reads/writes the real screen ViewModel through
`BacktestTimeRangeSource`.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TimeRangePicker.time_range_picker_dialog import (
    TimeRangePickerDialog,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_modals import (
    TimeRangePickerDialogWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)


class _Seed:
    """Stand-in for a screen's two text fields plus an active timeframe —
    the five `get_*` callables `TimeRangePickerDialog` forwards straight
    into `TimeRangePickerVM`."""

    def __init__(self, from_text: str, to_text: str) -> None:
        self.from_text = from_text
        self.to_text = to_text


@pytest.fixture
def seed():
    return _Seed("2026-07-01 00:00", "2026-07-08 00:00")


@pytest.fixture
def dialog(qapp, seed):
    built = TimeRangePickerDialog(
        get_from_text=lambda: seed.from_text,
        get_to_text=lambda: seed.to_text,
        get_timeframe_seconds=lambda: 300,
        get_timeframe_label=lambda: "5m",
    )
    yield built
    built.close()


def test_opening_seeds_the_body_from_the_screens_current_range(qapp, dialog):
    dialog.open_dialog()
    qapp.processEvents()

    assert dialog._widget_vm.fromText == "2026-07-01 00:00"
    assert dialog._widget_vm.toText == "2026-07-08 00:00"
    assert dialog._btn_apply.isEnabled() is True


def test_apply_enabled_tracks_canapply_across_preset_and_day_clicks(qapp, dialog):
    dialog.open_dialog()
    qapp.processEvents()

    dialog._widget_vm.choosePreset("all")
    qapp.processEvents()
    assert dialog._btn_apply.isEnabled() is True, (
        "ALL_HISTORY resolves to (None, None) on both ends, which "
        "TimeRangePickerVM.canApply treats as a complete, applicable choice"
    )

    dialog._widget_vm.selectDay("2026-07-10")
    qapp.processEvents()
    assert dialog._btn_apply.isEnabled() is False, (
        "a single day click sets only the start — canApply must go false "
        "until an end is also chosen"
    )


def test_applying_emits_the_chosen_pair_and_closes(qapp, dialog):
    received: list[tuple[str, str]] = []
    dialog.applied.connect(lambda start, end: received.append((start, end)))
    dialog.open_dialog()
    qapp.processEvents()

    dialog._widget_vm.choosePreset("7d")
    qapp.processEvents()
    dialog._widget_vm.apply()
    qapp.processEvents()

    assert len(received) == 1
    start, end = received[0]
    assert start and end
    assert not dialog.isVisible()


def test_cancel_closes_without_emitting(qapp, dialog):
    received: list[tuple[str, str]] = []
    dialog.applied.connect(lambda start, end: received.append((start, end)))
    dialog.open_dialog()
    qapp.processEvents()

    dialog.reject()
    qapp.processEvents()

    assert received == []
    assert not dialog.isVisible()


def test_a_broken_qml_file_raises_instead_of_rendering_a_blank_box(
    qapp, tmp_path, monkeypatch
):
    import Sagittarius_Elite_Warrior.src.presentation.ui.qml.TimeRangePicker.time_range_picker_dialog as host_module

    broken = tmp_path / "Broken.qml"
    broken.write_text("import QtQuick\nItem { this is not qml }\n")
    monkeypatch.setattr(host_module, "_QML", broken)

    with pytest.raises(RuntimeError, match="QML failed to load"):
        host_module.TimeRangePickerDialog(
            get_from_text=lambda: "",
            get_to_text=lambda: "",
            get_timeframe_seconds=lambda: 60,
            get_timeframe_label=lambda: "1m",
        )


# ---------------------------------------------------------------------- #
# Backtest's composition root — the one screen already wired at this point
# ---------------------------------------------------------------------- #


@pytest.fixture
def backtest_view_model():
    vm = BackTestViewModel()
    vm.timeRangePreset = "30d"
    vm.selectedTimeframe = "1h"
    return vm


def test_backtest_dialog_seeds_from_the_resolved_preset_range(
    qapp, backtest_view_model
):
    dialog = TimeRangePickerDialogWidget(backtest_view_model)
    dialog.open_dialog()
    qapp.processEvents()

    assert dialog._widget_vm.fromText != ""
    assert dialog._widget_vm.toText != ""
    dialog.close()


def test_backtest_dialog_applying_writes_an_explicit_custom_range(
    qapp, backtest_view_model
):
    dialog = TimeRangePickerDialogWidget(backtest_view_model)
    dialog.open_dialog()
    qapp.processEvents()

    dialog._widget_vm.choosePreset("7d")
    qapp.processEvents()
    dialog._widget_vm.apply()
    qapp.processEvents()

    assert backtest_view_model.timeRangePreset == "custom"
    assert backtest_view_model.customStartText != ""
    assert backtest_view_model.customEndText != ""
    assert not dialog.isVisible()
