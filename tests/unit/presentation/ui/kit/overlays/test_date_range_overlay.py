"""Tests for `widgets.overlays.date_range_overlay.DateRangeOverlay`."""

from __future__ import annotations

from datetime import date

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    DateRangeOverlay,
    Overlay,
    RangePreset,
)

_START = date(2026, 8, 19)
_END = date(2026, 8, 26)


def _overlay(qtbot, **kwargs) -> DateRangeOverlay:
    overlay = DateRangeOverlay("Range", start=_START, end=_END, **kwargs)
    qtbot.addWidget(overlay)
    return overlay


def test_it_is_an_overlay_holding_the_pair_it_was_given(qtbot):
    overlay = _overlay(qtbot)

    assert isinstance(overlay, Overlay)
    assert overlay.selected_range == (_START, _END)


def test_two_months_are_shown_side_by_side(qtbot):
    """One month makes a user page back and forth to see both ends of their
    own selection, and most ranges cross a month boundary."""
    overlay = _overlay(qtbot, month_name="{year}-{month:02d}")

    assert overlay._left_month.title == "2026-08"
    assert overlay._right_month.title == "2026-09"


def test_the_first_click_starts_a_fresh_pair_and_the_second_closes_it(qtbot):
    overlay = _overlay(qtbot)
    seen: list[tuple] = []
    overlay.range_changed.connect(lambda s, e: seen.append((s, e)))

    overlay._left_month.cell_for(date(2026, 8, 10)).click()
    assert overlay.selected_range == (date(2026, 8, 10), None)

    overlay._left_month.cell_for(date(2026, 8, 14)).click()
    assert overlay.selected_range == (date(2026, 8, 10), date(2026, 8, 14))
    assert seen[-1] == (date(2026, 8, 10), date(2026, 8, 14))


def test_clicking_before_the_start_restarts_rather_than_inverting(qtbot):
    """Silently swapping the ends would mean the same click does two
    different things depending on invisible state."""
    overlay = _overlay(qtbot)
    overlay._left_month.cell_for(date(2026, 8, 20)).click()

    overlay._left_month.cell_for(date(2026, 8, 5)).click()

    assert overlay.selected_range == (date(2026, 8, 5), None)


def test_choosing_does_not_close_the_dialog(qtbot):
    """Same call as `PickerOverlay`: the consumer's Confirm decides."""
    overlay = _overlay(qtbot)
    overlay.show()

    overlay._left_month.cell_for(date(2026, 8, 10)).click()

    assert overlay.isVisible()


def test_a_preset_with_a_span_moves_the_range(qtbot):
    overlay = _overlay(qtbot, presets=(RangePreset("Last 7 days", 7),))

    overlay._preset_buttons[0].click()

    assert overlay.selected_range == (date(2026, 8, 19), _END)


def test_a_preset_without_a_span_is_handed_back_to_the_consumer(qtbot):
    """`days=None` means "all of history" or "custom" — only the consumer
    knows where its data starts, so this class refuses to invent a date."""
    overlay = _overlay(qtbot, presets=(RangePreset("All history"),))
    chosen: list[str] = []
    overlay.preset_chosen.connect(chosen.append)

    overlay._preset_buttons[0].click()

    assert chosen == ["All history"]
    assert overlay.selected_range == (_START, _END)


def test_set_range_pages_the_calendar_to_the_new_start(qtbot):
    overlay = _overlay(qtbot, month_name="{year}-{month:02d}")

    overlay.set_range(date(2026, 1, 3), date(2026, 2, 9))

    assert overlay._left_month.title == "2026-01"
    assert overlay._right_month.title == "2026-02"


def test_paging_forward_from_december_rolls_the_year(qtbot):
    overlay = _overlay(qtbot, month_name="{year}-{month:02d}")
    overlay.show_months_from(date(2026, 12, 1))

    overlay._next.click()

    assert overlay._left_month.title == "2027-01"
    assert overlay._right_month.title == "2027-02"


def test_repaging_leaves_no_cell_of_the_previous_month_behind(qtbot):
    """Deletion is queued in Qt, so a cell only scheduled for it keeps its
    parent and keeps painting. The previous month's days stayed on screen
    over the new ones and over the weekday header.
    """
    overlay = _overlay(qtbot, month_name="{year}-{month:02d}")

    overlay.show_months_from(date(2026, 7, 1))

    live = [
        c
        for c in overlay._left_month.findChildren(
            type(overlay._left_month.cell_for(date(2026, 7, 15)))
        )
        if c.parent() is overlay._left_month
    ]
    assert len(live) == 6 * 7


def test_the_summary_is_the_consumers_sentence(qtbot):
    """It can count days; it cannot know a day of 1m candles is 1,440 rows."""
    overlay = _overlay(qtbot)

    overlay.summary = "7 days · 10,080 candles"

    assert overlay.summary == "7 days · 10,080 candles"


def test_confirm_and_cancel_are_reachable_and_answer_the_standard_way(qtbot):
    overlay = _overlay(qtbot, confirm_text="Apply", cancel_text="Cancel")
    overlay.show()

    overlay.confirm_button.click()

    assert overlay.result() == int(DateRangeOverlay.DialogCode.Accepted)


@pytest.mark.parametrize("month", [1, 6, 12])
def test_every_month_renders_a_full_six_week_grid(qtbot, month):
    """Fixed six rows, so paging cannot change the dialog's height."""
    overlay = _overlay(qtbot)
    overlay.show_months_from(date(2026, month, 1))

    assert len(overlay._left_month._cells) == 6 * 7
