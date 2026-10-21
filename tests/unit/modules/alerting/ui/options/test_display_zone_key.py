"""`EPIC-036D6` (review of PR #666) — the zone a quiet period is saved in is the display zone's
own name, never a label made from it: `SYSTEM` stays `SYSTEM`."""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.display_zone_key import (
    display_zone_key_of,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_preference import (
    DisplayTimezonePreference,
)


def _container(preference: DisplayTimezonePreference | None) -> Mock:
    container = Mock()
    registrations = {} if preference is None else {DisplayTimezonePreference: object}
    container.registrations.return_value = registrations
    container.resolve.return_value = preference
    return container


def test_system_stays_system_not_a_label_with_an_offset() -> None:
    preference = DisplayTimezonePreference()
    assert preference.set_zone("SYSTEM")

    assert display_zone_key_of(_container(preference))() == "SYSTEM"


def test_a_named_zone_is_its_own_name_and_the_choice_is_followed_at_each_call() -> None:
    preference = DisplayTimezonePreference()
    zone_key = display_zone_key_of(_container(preference))
    assert zone_key() == "UTC"

    preference.set_zone("Asia/Tokyo")

    assert zone_key() == "Asia/Tokyo"


def test_no_preference_registered_is_utc() -> None:
    assert display_zone_key_of(_container(None))() == "UTC"
