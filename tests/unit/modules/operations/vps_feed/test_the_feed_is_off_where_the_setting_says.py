"""`EPIC-047H` - a process whose setting turns the feed off (the GUI's) starts no worker and writes no file."""

from __future__ import annotations

from dataclasses import replace

from Sagittarius_Elite_Warrior.src.modules.operations.composition.vps_feed_host import (
    VpsFeedHost,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.vps_feed_settings import (
    VpsFeedSettings,
)


class _Container:
    """Resolves only the settings: anything the feed would build after them fails the test."""

    def __init__(self, settings: VpsFeedSettings) -> None:
        self._settings = settings

    def resolve(self, key: object) -> object:
        if key is VpsFeedSettings:
            return self._settings
        raise AssertionError(f"the feed built {key} although it is off")


class _Context:
    def __init__(self, container: _Container) -> None:
        self.container = container


def test_a_feed_turned_off_resolves_nothing_after_its_settings() -> None:
    off = replace(VpsFeedSettings.judged(120, 3.0, True), feed_enabled=False)

    VpsFeedHost().begin(_Context(_Container(off)), clock=None)  # type: ignore[arg-type]
