"""Which zone a quiet period is read in: the owner's display time zone (`EPIC-036D6`)."""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_preference import (
    find_display_timezone_preference,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
    get_system_timezone_name,
)
from sagittarius_engine.interfaces.i_container import IContainer

_SYSTEM = "SYSTEM"


def display_zone_key_of(container: IContainer) -> Callable[[], str]:
    """The zone name now: the chosen display zone (`SYSTEM` is the machine's own, by name), or
    `UTC` when the container holds no such setting. Asked at each save, so it follows the choice."""

    def zone_key() -> str:
        preference = find_display_timezone_preference(container)
        zone = DEFAULT_TIMEZONE if preference is None else preference.zone
        return get_system_timezone_name() if zone == _SYSTEM else zone

    return zone_key
