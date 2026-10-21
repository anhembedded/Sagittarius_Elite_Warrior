"""Set the quiet hours the Options page edits (`EPIC-036D6`).

Quiet hours hold INFO and WARNING and never CRITICAL (`QuietHoursHold`); this is where the owner
chooses the period. The period is read on the clock of the owner's display time zone at the time
of saving, kept as the zone's name: a later change of the display zone does not move a period
already set (it would move the night under the owner without a word).

Equal ends are refused rather than kept: `QuietHours` reads them as no period, and a form that
says "saved" over a period that never starts would be a lie (`QuietHours` docstring).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import time
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_quiet_hours_setting import (
    IQuietHoursSetting,
    QuietHoursChoice,
)

logger = logging.getLogger("App.Alerting")

#: What the form starts with when nothing is set: a night, the commonest quiet period.
DEFAULT_START = time(22, 0)
DEFAULT_END = time(7, 0)


class QuietHoursSave(Enum):
    SAVED = "saved"
    TURNED_OFF = "turned off"
    NO_PERIOD = "start and end are the same"
    READ_ONLY = "read-only copy"
    NOT_KEPT = "could not be kept"


@dataclass(frozen=True, slots=True)
class QuietHoursState:
    enabled: bool
    start: time
    end: time
    #: The zone the period is read in: the kept one, else the one a save would use now.
    zone_key: str
    #: `False` in a read-only copy, which cannot keep a change.
    editable: bool


class QuietHoursSetup:
    def __init__(
        self, setting: IQuietHoursSetting, zone_key: Callable[[], str]
    ) -> None:
        self._setting = setting
        self._zone_key = zone_key

    def state(self) -> QuietHoursState:
        kept = self._setting.quiet_hours()
        editable = not self._setting.read_only
        if kept is None:
            return QuietHoursState(
                False, DEFAULT_START, DEFAULT_END, self._zone_key(), editable
            )
        return QuietHoursState(True, kept.start, kept.end, kept.zone_key, editable)

    def set_period(self, start: time, end: time) -> QuietHoursSave:
        """Keeps `start` to `end` in the display zone as it is now."""
        if self._setting.read_only:
            return self._told(QuietHoursSave.READ_ONLY)
        if start == end:
            return self._told(QuietHoursSave.NO_PERIOD)
        return self._keep(QuietHoursChoice(start, end, self._zone_key()))

    def turn_off(self) -> QuietHoursSave:
        if self._setting.read_only:
            return self._told(QuietHoursSave.READ_ONLY)
        return self._keep(None)

    def _keep(self, choice: QuietHoursChoice | None) -> QuietHoursSave:
        try:
            self._setting.set_quiet_hours(choice)
        except OSError as exc:
            logger.warning(
                "[alert-setup] quiet hours could not be kept (%s)", type(exc).__name__
            )
            return self._told(QuietHoursSave.NOT_KEPT)
        return self._told(
            QuietHoursSave.TURNED_OFF if choice is None else QuietHoursSave.SAVED
        )

    @staticmethod
    def _told(outcome: QuietHoursSave) -> QuietHoursSave:
        logger.info("[alert-setup] quiet hours: %s", outcome.value)
        return outcome
