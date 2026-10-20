"""`BOT-205` — the Backtest's view model and the application's display time zone are one
choice: a pick on either side reaches the other, once."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.shared_display_timezone import (
    follow_shared_display_timezone,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.view_models.time_range_view_model import (
    TimeRangeViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_preference import (
    DisplayTimezonePreference,
)


def test_it_takes_the_shared_zone_at_once(qapp) -> None:
    preference = DisplayTimezonePreference()
    preference.set_zone("Asia/Tokyo")
    time_range = TimeRangeViewModel()

    follow_shared_display_timezone(time_range, preference)

    assert time_range.displayTimezone == "Asia/Tokyo"


def test_a_pick_in_the_run_setup_reaches_the_shared_zone(qapp) -> None:
    preference = DisplayTimezonePreference()
    time_range = TimeRangeViewModel()
    follow_shared_display_timezone(time_range, preference)

    time_range.set_display_timezone("SYSTEM")

    assert preference.zone == "SYSTEM"


def test_a_pick_on_another_screen_reaches_the_view_model_and_announces_it_once(
    qapp,
) -> None:
    preference = DisplayTimezonePreference()
    time_range = TimeRangeViewModel()
    follow_shared_display_timezone(time_range, preference)
    announced: list[str] = []
    time_range.displayTimezoneChanged.connect(
        lambda: announced.append(time_range.displayTimezone)
    )

    preference.set_zone("Europe/London")

    assert announced == ["Europe/London"]
