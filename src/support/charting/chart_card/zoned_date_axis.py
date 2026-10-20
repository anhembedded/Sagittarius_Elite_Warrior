"""A chart's time axis in the application's display time zone, one instant at a time.

Capability: Draw a chart's time axis in the display time zone
    Also: date axis, time axis, chart ticks, daylight saving, utc offset
    Use: ZonedDateAxisItem
    User: src/support/charting/chart_card/plot_layout.py
    Status: stable
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import pyqtgraph as pg
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_service import (
    format_display_timestamp,
    get_utc_offset_seconds,
)


class ZonedDateAxisItem(pg.DateAxisItem):
    """`pg.DateAxisItem` takes one `utcOffset` for every tick, so a view across a
    daylight-saving change read one side of it an hour off, and its sign is seconds *west* of
    UTC, which the chart passed as seconds east (`BUG-240`). Every label here is the tick's own
    instant converted by `to_display_time`, the converter the crosshair and the tables use.
    The offset pyqtgraph still takes only places the ticks on round local hours and days: it is
    the one in force at the middle of the view, in pyqtgraph's sign."""

    def __init__(self, zone: str, **kwargs: object) -> None:
        super().__init__(orientation="bottom", **kwargs)
        self._zone = zone
        self.utcOffset = self._seconds_west_of_utc(datetime.now(UTC).timestamp())

    @property
    def display_zone(self) -> str:
        return self._zone

    def set_display_zone(self, zone: str) -> None:
        self._zone = zone
        self.picture = None
        self.update()

    def tickValues(
        self, minVal: float, maxVal: float, size: float
    ) -> list[tuple[float, list[float]]]:
        self.utcOffset = self._seconds_west_of_utc((minVal + maxVal) / 2)
        return super().tickValues(minVal, maxVal, size)

    def tickStrings(
        self, values: Sequence[float], scale: float, spacing: float
    ) -> list[str]:
        tick_spec = next(
            (spec for spec in self.zoomLevel.tickSpecs if spec.spacing == spacing),
            None,
        )
        if tick_spec is None:
            return super().tickStrings(values, scale, spacing)
        return [self._label(value, tick_spec.format) for value in values]

    def _seconds_west_of_utc(self, timestamp: float) -> float:
        return -get_utc_offset_seconds(timestamp, self._zone)

    def _label(self, timestamp: float, text_format: str) -> str:
        text = format_display_timestamp(timestamp, self._zone, text_format)
        if "%f" in text_format:
            return text[:-3]  # pyqtgraph writes milliseconds only
        if "%Y" in text_format:
            return text.lstrip("0")
        return text
