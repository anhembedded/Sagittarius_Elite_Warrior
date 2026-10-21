"""Which zone a quiet period is read in: the owner's display time zone (`EPIC-036D6`)."""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_preference import (
    find_display_timezone_preference,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
)
from sagittarius_engine.interfaces.i_container import IContainer


def display_zone_key_of(container: IContainer) -> Callable[[], str]:
    """The display zone's name now: `UTC`, `SYSTEM` (the machine's own clock, which has no name
    the standard library can read) or an IANA key; `UTC` when the container holds no such
    setting. Asked at each save, so it follows the choice."""

    def zone_key() -> str:
        preference = find_display_timezone_preference(container)
        return DEFAULT_TIMEZONE if preference is None else preference.zone

    return zone_key
