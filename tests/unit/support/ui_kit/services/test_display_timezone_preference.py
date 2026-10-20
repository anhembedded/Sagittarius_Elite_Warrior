"""`BOT-205` — the one display time zone every screen follows, and remembers."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_preference import (
    DisplayTimezonePreference,
    find_display_timezone_preference,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
    SYSTEM_TIMEZONE_KEY,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.i_state_contributor import (
    IStateContributor,
)


class _Container:
    def __init__(self, held: object | None) -> None:
        self._held = held

    def registrations(self) -> dict[type, object]:
        return {} if self._held is None else {DisplayTimezonePreference: self._held}

    def resolve(self, _key: type) -> object | None:
        return self._held


def test_it_starts_in_utc() -> None:
    assert DisplayTimezonePreference().zone == DEFAULT_TIMEZONE


def test_a_change_tells_its_listeners_and_the_owner_once() -> None:
    changes: list[str] = []
    marked: list[bool] = []
    preference = DisplayTimezonePreference(on_changed=lambda: marked.append(True))
    preference.subscribe(changes.append)

    assert preference.set_zone(SYSTEM_TIMEZONE_KEY)
    assert not preference.set_zone(SYSTEM_TIMEZONE_KEY)

    assert changes == [SYSTEM_TIMEZONE_KEY]
    assert marked == [True]


def test_a_zone_no_picker_offers_is_refused() -> None:
    preference = DisplayTimezonePreference()

    assert not preference.set_zone("Mars/Olympus_Mons")
    assert preference.zone == DEFAULT_TIMEZONE


def test_an_unsubscribed_listener_hears_nothing_more() -> None:
    changes: list[str] = []
    preference = DisplayTimezonePreference()
    stop = preference.subscribe(changes.append)
    stop()

    preference.set_zone("Asia/Tokyo")

    assert changes == []


def test_the_choice_is_remembered_across_sessions() -> None:
    first = DisplayTimezonePreference()
    first.set_zone("Asia/Ho_Chi_Minh")
    assert isinstance(first, IStateContributor)

    second = DisplayTimezonePreference()
    second.restore_state(first.capture_state())

    assert second.zone == "Asia/Ho_Chi_Minh"


def test_a_remembered_zone_that_is_gone_degrades_to_utc_without_a_word() -> None:
    changes: list[str] = []
    preference = DisplayTimezonePreference()
    preference.subscribe(changes.append)

    preference.restore_state({"zone": "Atlantis/Lost"})

    assert preference.zone == DEFAULT_TIMEZONE
    assert changes == []


def test_find_returns_the_registered_one_and_none_otherwise() -> None:
    preference = DisplayTimezonePreference()

    assert find_display_timezone_preference(_Container(preference)) is preference
    assert find_display_timezone_preference(_Container(None)) is None
    assert find_display_timezone_preference(_Container(object())) is None
