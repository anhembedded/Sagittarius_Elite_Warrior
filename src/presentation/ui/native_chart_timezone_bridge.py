"""BOT-098F6C — exposes the app's one timezone-formatting implementation to
QML, instead of reimplementing IANA/fallback rules a second time in JS.

The native ABI's `timestampUtcMs` fields are always raw UTC; this bridge
converts to the selected display timezone only at the presentation
boundary, mirroring `display_timezone_service.format_display_timestamp`
exactly (including its silent-fallback-to-UTC behavior for an unresolvable
timezone name).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Slot

from Sagittarius_Elite_Warrior.src.presentation.ui.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
    format_display_timestamp,
)


class NativeChartTimezoneBridge(QObject):
    """Registered as a QML context property (e.g. `timezoneBridge`) so
    `NativeBacktestChart.qml` can format axis/tooltip timestamps without
    owning any timezone logic itself."""

    @Slot(int, str, result=str)
    def formatTimestamp(
        self, timestamp_utc_ms: int, tz_name: str = DEFAULT_TIMEZONE
    ) -> str:
        return format_display_timestamp(timestamp_utc_ms / 1000.0, tz_name=tz_name)

    @Slot(int, str, result=str)
    def formatAxisTime(
        self, timestamp_utc_ms: int, tz_name: str = DEFAULT_TIMEZONE
    ) -> str:
        """Shorter form for the time-axis ticks (no seconds/date)."""
        return format_display_timestamp(
            timestamp_utc_ms / 1000.0, tz_name=tz_name, fmt="%H:%M"
        )
