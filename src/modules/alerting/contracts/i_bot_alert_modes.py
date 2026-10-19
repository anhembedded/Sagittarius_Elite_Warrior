"""`IBotAlertModes` — what the owner says each bot may tell (`BOT-191`, `N5`).

The Options page edits through this port; the hub reads the result through
`IAlertSettingsSource`, so an edit applies to the next alert without a restart.
Both are served by one object, so the two can never disagree.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.bot_alert_mode import (
    BotAlertMode,
)


class IBotAlertModes(ABC):
    @abstractmethod
    def modes(self) -> Mapping[str, BotAlertMode]:
        """The modes set so far; a bot not in it is `ON`."""

    @abstractmethod
    def set_mode(self, bot_id: str, mode: BotAlertMode) -> None:
        """Sets and keeps `bot_id`'s mode. Raises `OSError` when it cannot be kept."""
