"""Tests for `components.date_range_picker.pick_date_range`."""

from __future__ import annotations

import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.components import date_range_picker
from Sagittarius_Elite_Warrior.src.presentation.ui.components.date_range_picker import (
    pick_date_range,
)
from sagittarius_engine.extensions.pyside_mvc.widgets import DateRangeOverlay


class _Captured:
    """Runs the dialog without blocking: replaces `exec()` with a callback
    that drives the overlay and returns a result code."""

    def __init__(self, monkeypatch, drive, accepted=True):
        self.overlay: DateRangeOverlay | None = None
        code = (
            DateRangeOverlay.DialogCode.Accepted
            if accepted
            else DateRangeOverlay.DialogCode.Rejected
        )

        def fake_exec(overlay_self):
            self.overlay = overlay_self
            drive(overlay_self)
            return code

        monkeypatch.setattr(DateRangeOverlay, "exec", fake_exec, raising=False)


def test_it_returns_the_pair_in_the_apps_own_format(qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    captured = _Captured(
        monkeypatch, lambda o: o.set_range(date(2026, 3, 2), date(2026, 3, 9))
    )

    result = pick_date_range(
        parent, start_text="2026-08-19 06:56", end_text="2026-08-26 06:56"
    )

    assert result == ("2026-03-02 06:56", "2026-03-09 06:56")
    assert captured.overlay is not None


def test_the_time_of_day_from_each_field_survives(qtbot, monkeypatch):
    """Only the dates are picked; a user who set 06:56 keeps 06:56."""
    parent = QWidget()
    qtbot.addWidget(parent)
    _Captured(monkeypatch, lambda o: o.set_range(date(2026, 3, 2), date(2026, 3, 9)))

    start, end = pick_date_range(
        parent, start_text="2026-08-19 01:30", end_text="2026-08-26 23:45"
    )

    assert start.endswith("01:30")
    assert end.endswith("23:45")


def test_cancelling_changes_nothing(qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    _Captured(monkeypatch, lambda o: None, accepted=False)

    assert (
        pick_date_range(
            parent, start_text="2026-08-19 06:56", end_text="2026-08-26 06:56"
        )
        is None
    )


def test_an_unparseable_field_still_opens_the_calendar(qtbot, monkeypatch):
    """A half-typed date is the ordinary state of a text field, and it is
    exactly when a user most wants the calendar — refusing to open would be
    backwards."""
    parent = QWidget()
    qtbot.addWidget(parent)
    captured = _Captured(monkeypatch, lambda o: None, accepted=False)

    pick_date_range(parent, start_text="2026-08-1", end_text="")

    assert captured.overlay is not None
    start, end = captured.overlay.selected_range
    assert (end - start).days == date_range_picker._FALLBACK_DAYS


def test_a_reversed_pair_is_reseeded_rather_than_shown_backwards(qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    captured = _Captured(monkeypatch, lambda o: None, accepted=False)

    pick_date_range(
        parent, start_text="2026-08-26 00:00", end_text="2026-08-19 00:00"
    )

    start, end = captured.overlay.selected_range
    assert start < end


def test_the_summary_counts_one_minute_candles(qtbot, monkeypatch):
    """The engine can count days; only this app knows a day is 1,440 rows."""
    parent = QWidget()
    qtbot.addWidget(parent)
    captured = _Captured(monkeypatch, lambda o: None, accepted=False)

    pick_date_range(
        parent, start_text="2026-08-19 00:00", end_text="2026-08-26 00:00"
    )

    assert "10,080 nến 1m" in captured.overlay.summary


def test_an_open_pair_says_so_instead_of_counting(qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    captured = _Captured(
        monkeypatch,
        lambda o: o._left_month.cell_for(date(2026, 8, 10)).click(),
        accepted=False,
    )

    pick_date_range(
        parent, start_text="2026-08-19 00:00", end_text="2026-08-26 00:00"
    )

    assert captured.overlay.summary == "Chọn ngày kết thúc"
