"""`BUG-240`: a chart's time axis reads each tick in the offset in force at that tick.

The axis took one UTC offset, computed at `now`, for every tick, so a view across a
daylight-saving change labelled the ticks on the far side of it an hour off. The layout is
the production one (`ChartPlotLayout`), the zone a real IANA zone, so no test depends on
the runner's `TZ`."""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from PySide6.QtGui import QImage, QPainter
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.plot_layout import (
    ChartPlotLayout,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services import (
    display_timezone_service as service,
)

#: New York moved from EST (UTC-05:00) to EDT (UTC-04:00) at 2026-03-08 07:00Z.
_VIEW_START = datetime(2026, 3, 8, 3, 0, tzinfo=UTC).timestamp()
_VIEW_END = datetime(2026, 3, 8, 15, 0, tzinfo=UTC).timestamp()
_WIDTH_PX = 800


def _machine_in_new_york(moment: datetime) -> datetime:
    """What the OS answers on a machine set to New York: the fixed-offset zone
    `datetime.astimezone()` returns, per instant."""
    local = moment.astimezone(ZoneInfo("America/New_York"))
    offset = local.utcoffset()
    assert offset is not None
    return local.astimezone(timezone(offset, local.tzname()))


def _drawn_labels(layout: ChartPlotLayout) -> list[str]:
    """The labels the axis draws for the visible range, from its own tick generation."""
    axis = layout.main_plot.getAxis("bottom")
    image = QImage(_WIDTH_PX, 100, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        _, _, text_specs = axis.generateDrawSpecs(painter)
    finally:
        painter.end()
    return [text for _, _, text in text_specs]


def _axis_labels(layout: ChartPlotLayout) -> list[str]:
    layout.widget.resize(_WIDTH_PX, 400)
    layout.main_plot.setXRange(_VIEW_START, _VIEW_END, padding=0)
    layout.widget.grab()
    return _drawn_labels(layout)


@pytest.mark.parametrize("zone", ["America/New_York", "SYSTEM"])
def test_every_tick_reads_in_the_offset_of_its_own_instant(
    qapp: object, monkeypatch: pytest.MonkeyPatch, zone: str
) -> None:
    monkeypatch.setattr(service, "machine_local_time", _machine_in_new_york)
    layout = ChartPlotLayout()
    try:
        layout.set_display_timezone(zone)

        labels = _axis_labels(layout)

        # 22:00 EST on 7 March .. 11:00 EDT on 8 March: local 02:00 does not exist that day.
        assert "01:00" in labels
        assert "03:00" in labels
        assert "02:00" not in labels
    finally:
        layout.widget.deleteLater()


def test_an_east_zone_reads_ahead_of_utc_not_behind_it(qapp: object) -> None:
    """Vietnam is UTC+7: 00:00Z reads 07:00, so the 01:00Z tick reads 08:00. The axis once read 18:00 of the day before."""
    layout = ChartPlotLayout()
    try:
        layout.set_display_timezone("Asia/Ho_Chi_Minh")
        start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC).timestamp()
        layout.widget.resize(_WIDTH_PX, 400)
        layout.main_plot.setXRange(start, start + 8 * 3600, padding=0)
        layout.widget.grab()

        labels = _drawn_labels(layout)

        assert "08:00" in labels
        assert "18:00" not in labels
    finally:
        layout.widget.deleteLater()


@pytest.mark.parametrize("zone", ["Asia/Ho_Chi_Minh", "America/New_York"])
def test_day_ticks_sit_on_the_local_midnight_of_the_zone(
    qapp: object, zone: str
) -> None:
    """Placement uses pyqtgraph's own sign (seconds west of UTC): a zone east of UTC with the
    sign reversed puts a day tick 14 hours from local midnight, and its `%d` label hides it."""
    layout = ChartPlotLayout()
    try:
        layout.set_display_timezone(zone)
        start = datetime(2026, 1, 10, 0, 0, tzinfo=UTC).timestamp()
        end = start + 3 * 86400
        layout.widget.resize(_WIDTH_PX, 400)
        layout.main_plot.setXRange(start, end, padding=0)
        layout.widget.grab()
        _drawn_labels(layout)  # lets the axis measure its font, as a paint does
        axis = layout.main_plot.getAxis("bottom")

        day_ticks = [
            tick
            for spacing, ticks in axis.tickValues(start, end, _WIDTH_PX)
            if spacing == 86400
            for tick in ticks
        ]

        assert len(day_ticks) >= 2
        for tick in day_ticks:
            local = service.to_display_time(datetime.fromtimestamp(tick, UTC), zone)
            assert (local.hour, local.minute) == (0, 0)
    finally:
        layout.widget.deleteLater()


def test_a_view_at_the_edge_of_the_calendar_draws_instead_of_raising(
    qapp: object,
) -> None:
    layout = ChartPlotLayout()
    try:
        layout.set_display_timezone("America/New_York")
        first = datetime(1, 1, 1, tzinfo=UTC).timestamp()
        layout.widget.resize(_WIDTH_PX, 400)
        layout.main_plot.setXRange(first, first + 3600, padding=0)
        layout.widget.grab()

        _drawn_labels(layout)
    finally:
        layout.widget.deleteLater()
