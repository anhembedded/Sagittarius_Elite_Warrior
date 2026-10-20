"""`BOT-205` — the drop-down that chooses the display time zone."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.ui_kit.display_timezone_combo import (
    DisplayTimezoneCombo,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_preference import (
    DisplayTimezonePreference,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_service import (
    SYSTEM_TIMEZONE_KEY,
    get_supported_timezones,
)


def test_it_offers_the_zones_the_backtest_offers_with_the_current_one_selected(
    qapp,
) -> None:
    preference = DisplayTimezonePreference()
    preference.set_zone("Asia/Tokyo")

    combo = DisplayTimezoneCombo(preference)

    assert [combo.itemData(i) for i in range(combo.count())] == [
        option["id"] for option in get_supported_timezones()
    ]
    assert combo.currentData() == "Asia/Tokyo"


def test_a_persons_choice_writes_the_preference(qapp) -> None:
    preference = DisplayTimezonePreference()
    combo = DisplayTimezoneCombo(preference)

    combo.activated.emit(combo.findData(SYSTEM_TIMEZONE_KEY))

    assert preference.zone == SYSTEM_TIMEZONE_KEY


def test_a_choice_made_elsewhere_moves_the_selection_without_writing_back(
    qapp,
) -> None:
    preference = DisplayTimezonePreference()
    combo = DisplayTimezoneCombo(preference)
    heard: list[str] = []
    preference.subscribe(heard.append)

    preference.set_zone("Europe/London")

    assert combo.currentData() == "Europe/London"
    assert heard == ["Europe/London"]
