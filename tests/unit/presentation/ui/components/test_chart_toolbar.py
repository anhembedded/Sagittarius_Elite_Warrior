"""Tests for `ChartToolbar` — the five quick pills plus the full picker.

`EPIC-014`: this row is a real timeframe selector on both screens that show a
chart, and its five pills were the only way to change one. A timeframe outside
them left every pill unselected and the user with no way back to it.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.chart_toolbar import (
    DEFAULT_TIMEFRAMES,
    ChartToolbar,
)


def test_the_quick_pills_stay_five(qapp):
    """The row lives in a chart header; sixteen pills would not fit. That
    constraint is real and the `…` button is what resolves it."""
    toolbar = ChartToolbar()

    assert len(toolbar._buttons) == len(DEFAULT_TIMEFRAMES) == 5


def test_clicking_a_pill_selects_it_and_emits(qapp):
    toolbar = ChartToolbar()
    emitted: list[str] = []
    toolbar.sig_timeframe_changed.connect(emitted.append)

    toolbar._buttons["1h"].click()
    qapp.processEvents()

    assert emitted == ["1h"]
    assert toolbar._buttons["1h"].isChecked() is True
    assert toolbar._btn_more.isChecked() is False


def test_a_timeframe_with_no_pill_is_shown_on_the_more_button(qapp):
    """Reachable on every launch: EPIC-010D restores a remembered interval
    and DEFAULT_INTERVAL can name any of the sixteen. Before this the row
    simply showed no selection at all."""
    toolbar = ChartToolbar()

    toolbar.set_active("4h")

    assert toolbar._btn_more.text() == "4h"
    assert toolbar._btn_more.isChecked() is True
    assert not any(btn.isChecked() for btn in toolbar._buttons.values())


def test_returning_to_a_pill_clears_the_more_button(qapp):
    toolbar = ChartToolbar()
    toolbar.set_active("12h")
    assert toolbar._btn_more.text() == "12h"

    toolbar.set_active("5m")

    assert toolbar._btn_more.text() == "…"
    assert toolbar._btn_more.isChecked() is False
    assert toolbar._buttons["5m"].isChecked() is True


def test_the_more_button_opens_a_picker_over_every_domain_timeframe(qapp):
    toolbar = ChartToolbar()

    toolbar._btn_more.click()
    qapp.processEvents()

    picker = toolbar._picker
    assert picker is not None
    codes = [card.option.code for card in picker._cards]
    assert sorted(codes) == sorted(member.value for member in TimeFrame)
    picker.close()


def test_choosing_from_the_picker_emits_the_same_signal_as_a_pill(qapp):
    """The consumer wiring does not change: Backtest and Dev Board still
    connect only `sig_timeframe_changed`, which is why neither had to grow a
    copy of this dialog."""
    toolbar = ChartToolbar()
    emitted: list[str] = []
    toolbar.sig_timeframe_changed.connect(emitted.append)

    toolbar._btn_more.click()
    qapp.processEvents()
    card = next(c for c in toolbar._picker._cards if c.option.code == "3d")
    card.clicked.emit()
    qapp.processEvents()

    assert emitted == ["3d"]
    assert toolbar._btn_more.text() == "3d"


def test_every_button_is_a_visible_click_target(qapp):
    """Reported as "the … button is missing" — it was not missing, it was
    **13x19 px**: `_button_style` set `padding: 2px 0`, so each button
    collapsed to the width of its own glyphs, and a bare ellipsis in muted
    grey at that size reads as a separator rather than a control.

    Measured, not eyeballed: this asserts the laid-out width, which is what
    was actually wrong. A test on `setMinimumWidth` alone would have passed
    against the broken build too, since the collapse came from the padding.
    """
    toolbar = ChartToolbar()
    toolbar.resize(toolbar.sizeHint())
    toolbar.show()
    qapp.processEvents()

    assert toolbar._btn_more.width() >= ChartToolbar._BUTTON_MIN_WIDTH
    for code, button in toolbar._buttons.items():
        assert button.width() >= ChartToolbar._BUTTON_MIN_WIDTH, code
    toolbar.close()


def test_an_off_pill_code_fits_inside_the_more_button(qapp):
    """`12h` is the widest thing that button ever shows."""
    toolbar = ChartToolbar()
    toolbar.set_active("12h")
    toolbar.resize(toolbar.sizeHint())
    toolbar.show()
    qapp.processEvents()

    assert toolbar._btn_more.text() == "12h"
    assert toolbar._btn_more.width() <= ChartToolbar._BUTTON_MAX_WIDTH
    assert toolbar._btn_more.sizeHint().width() <= toolbar._btn_more.width(), (
        "the code is clipped"
    )
    toolbar.close()


def test_dismissing_the_picker_leaves_the_row_as_it_was(qapp):
    """`clicked` on a checkable button toggles it before the slot runs, so
    opening the dialog and cancelling used to leave `…` lit alongside the
    pill that was actually active — two things looking selected at once."""
    toolbar = ChartToolbar()
    toolbar.set_active("1m")
    emitted: list[str] = []
    toolbar.sig_timeframe_changed.connect(emitted.append)

    toolbar._btn_more.click()
    qapp.processEvents()
    toolbar._picker.reject()
    qapp.processEvents()

    assert toolbar._btn_more.isChecked() is False
    assert toolbar._btn_more.text() == "…"
    assert toolbar._buttons["1m"].isChecked() is True
    assert emitted == [], "dismissing chooses nothing"
