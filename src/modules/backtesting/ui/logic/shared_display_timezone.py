"""`BOT-205` — the Backtest screen reads and writes the application's display time zone.

The zone used to be the Backtest's own remembered field. It is the person's clock, so it is one
shared `DisplayTimezonePreference` now and the Backtest's view model follows it in both
directions: the Run setup combo writes the view model, which writes the preference; a choice made
on another screen reaches the view model, which tells the chart and the trade table as before.
Each side sets only what differs, so the two never answer each other in a loop.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_preference import (
    DisplayTimezonePreference,
)

from ..view_models.time_range_view_model import TimeRangeViewModel


def follow_shared_display_timezone(
    time_range: TimeRangeViewModel, preference: DisplayTimezonePreference
) -> None:
    """Takes the preference's zone now and keeps both in step from here."""
    time_range.set_display_timezone(preference.zone)
    time_range.displayTimezoneChanged.connect(
        lambda: preference.set_zone(time_range.displayTimezone)
    )
    preference.subscribe(time_range.set_display_timezone)
