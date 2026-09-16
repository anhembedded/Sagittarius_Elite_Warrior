"""`TimeRangePickerDialog`, rendered for real — `EPIC-025` PR 4.3d.

## Restated, and the sentence that used to be here is why `CS-004` exists

This file opened: *"`TimeRangePickerVM`'s own rules already have full coverage
with no `QApplication` at all (`qml/TimeRangePicker/tests/...`)"*. True about
that file and false about the gate, which runs `pytest
Sagittarius_Elite_Warrior/tests` and never collected it — the blind spot
`BUG-128` cost something for and `test_no_test_file_lives_under_src.py` now
guards. The rules have a suite the gate runs at `test_range_rules.py`, beside
this one.

What only a test building the real dialog can prove is the **wiring**: the
footer tracks "both ends or neither", `applied` closes, and every control
writes the same pair. The preset maths and the summary are
`test_range_rules.py`'s.

Restated one for one from `qml/test_time_range_picker_dialog_host.py`, which
had seven: five keep their names, `test_apply_enabled_tracks_canapply_across_preset_and_day_clicks`
becomes two (the "all history" state, and the inverted one two calendars made
reachable), and the seventh — that a broken `.qml` raises instead of rendering a
blank box — is dropped because it has no subject now.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QDate
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_modals import (
    TimeRangePickerDialogWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.time_range_picker import (
    RangePresetKind,
    TimeRangePickerDialog,
)


class _Seed:
    """Stand-in for a screen's two text fields plus an active timeframe — the
    five `get_*` callables the dialog reads its state through."""

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

    assert dialog._from_field.dateTime().toString("yyyy-MM-dd HH:mm") == (
        "2026-07-01 00:00"
    )
    assert dialog._to_field.dateTime().toString("yyyy-MM-dd HH:mm") == (
        "2026-07-08 00:00"
    )
    assert dialog._from_calendar.selectedDate().toString("yyyy-MM-dd") == "2026-07-01"
    assert dialog._btn_apply.isEnabled() is True


def test_all_history_disables_the_calendars_and_still_applies(qapp, dialog):
    """`(None, None)` is a complete choice — "no limit" — so Apply stays live,
    and the two calendars go insensitive because there is no date to pick.

    The old one-grid picker could reach "only a start chosen", which is the
    state Apply had to refuse. Two calendars cannot: each holds one end, and
    the only way to have neither is this preset. They reach a *different*
    invalid state instead, which the next test is about."""
    dialog.open_dialog()
    qapp.processEvents()

    dialog._choose_preset(RangePresetKind.ALL_HISTORY)
    qapp.processEvents()

    assert dialog._btn_apply.isEnabled() is True
    assert dialog._from_calendar.isEnabled() is False
    assert dialog._to_calendar.isEnabled() is False
    assert "All history" in dialog._summary_label.text()


def test_clicking_a_start_after_the_end_refuses_to_apply_and_says_why(qapp, dialog):
    """`BUG-128` reached the user as a *seeded* inverted pair; two calendars
    give the user a second way to the same state, and that one is a click.

    Driven through `QCalendarWidget.clicked`, the signal a click emits, so the
    connection in `_calendar()` is part of what this test holds: disconnect it
    and the pair never inverts.
    """
    dialog.open_dialog()
    qapp.processEvents()

    dialog._from_calendar.clicked.emit(QDate(2026, 7, 20))
    qapp.processEvents()

    assert dialog._btn_apply.isEnabled() is False
    assert "end is before the start" in dialog._summary_label.text()

    # And the user recovers by moving the other end, with no reopen needed.
    dialog._to_calendar.clicked.emit(QDate(2026, 7, 25))
    qapp.processEvents()

    assert dialog._btn_apply.isEnabled() is True


def test_applying_emits_the_chosen_pair_and_closes(qapp, dialog):
    received: list[tuple[str, str]] = []
    dialog.applied.connect(lambda start, end: received.append((start, end)))
    dialog.open_dialog()
    qapp.processEvents()

    dialog._choose_preset(RangePresetKind.LAST_7_DAYS)
    qapp.processEvents()
    dialog._btn_apply.click()
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


# ---------------------------------------------------------------------- #
# Backtest's composition root — the one screen already wired at this point
# ---------------------------------------------------------------------- #


@pytest.fixture
def backtest_view_model():
    vm = BackTestViewModel()
    vm.time_range.preset = "30d"
    vm.selectedTimeframe = "1h"
    return vm


def test_backtest_dialog_seeds_from_the_resolved_preset_range(
    qapp, backtest_view_model
):
    dialog = TimeRangePickerDialogWidget(backtest_view_model)
    dialog.open_dialog()
    qapp.processEvents()

    assert dialog._from_field.dateTime().isValid()
    assert dialog._to_field.dateTime().isValid()
    assert dialog._btn_apply.isEnabled() is True
    dialog.close()


def test_backtest_dialog_applying_writes_an_explicit_custom_range(
    qapp, backtest_view_model
):
    dialog = TimeRangePickerDialogWidget(backtest_view_model)
    dialog.open_dialog()
    qapp.processEvents()

    dialog._choose_preset(RangePresetKind.LAST_7_DAYS)
    qapp.processEvents()
    dialog._btn_apply.click()
    qapp.processEvents()

    assert backtest_view_model.time_range.preset == "custom"
    assert backtest_view_model.time_range.customStartText != ""
    assert backtest_view_model.time_range.customEndText != ""
    assert not dialog.isVisible()
