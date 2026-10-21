"""Set how often the heartbeat is sent, from the Options page (`EPIC-036D9`).

The owner chooses among `HEARTBEAT_HOURS_CHOICES`. Choosing the default (N4: six hours) keeps no
value at all, so a later change of the default still reaches an owner who never chose a different
one (as for a routing cell, `EPIC-036D7`). A shorter interval than the last heartbeat's age sends
the next one at the next housekeeping pass; a longer one waits.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_heartbeat_setting import (
    IHeartbeatSetting,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    DEFAULT_HEARTBEAT,
    HEARTBEAT_HOURS_CHOICES,
)

logger = logging.getLogger("App.Alerting")

#: The default interval, in whole hours.
DEFAULT_HOURS = int(DEFAULT_HEARTBEAT.heartbeat_every.total_seconds() // 3600)


class HeartbeatSave(Enum):
    SAVED = "saved"
    BACK_TO_DEFAULT = "back to the default"
    NOT_A_CHOICE = "not one of the choices"
    READ_ONLY = "read-only copy"
    NOT_KEPT = "could not be kept"


@dataclass(frozen=True, slots=True)
class HeartbeatState:
    #: The interval in force, in whole hours: the chosen one, else the default.
    hours: int
    #: What the owner may choose between, in order.
    choices: tuple[int, ...]
    #: `False` in a read-only copy, which cannot keep a change.
    editable: bool


class HeartbeatSetup:
    def __init__(self, setting: IHeartbeatSetting) -> None:
        self._setting = setting

    def state(self) -> HeartbeatState:
        kept = self._setting.heartbeat_hours()
        return HeartbeatState(
            DEFAULT_HOURS if kept is None else kept,
            HEARTBEAT_HOURS_CHOICES,
            not self._setting.read_only,
        )

    def set_hours(self, hours: int) -> HeartbeatSave:
        if self._setting.read_only:
            return self._told(HeartbeatSave.READ_ONLY)
        if hours not in HEARTBEAT_HOURS_CHOICES:
            return self._told(HeartbeatSave.NOT_A_CHOICE)
        is_default = hours == DEFAULT_HOURS
        try:
            self._setting.set_heartbeat_hours(None if is_default else hours)
        except OSError as exc:
            logger.warning(
                "[alert-setup] the heartbeat interval could not be kept (%s)",
                type(exc).__name__,
            )
            return self._told(HeartbeatSave.NOT_KEPT)
        return self._told(
            HeartbeatSave.BACK_TO_DEFAULT if is_default else HeartbeatSave.SAVED
        )

    @staticmethod
    def _told(outcome: HeartbeatSave) -> HeartbeatSave:
        logger.info("[alert-setup] heartbeat: %s", outcome.value)
        return outcome
