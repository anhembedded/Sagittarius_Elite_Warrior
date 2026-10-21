"""`IQuietHoursSetting` — the quiet hours the owner set (`EPIC-036D6`).

The Options page edits through this port; the hub reads the result as `AlertSettings.quiet_hours`
through `IAlertSettingsSource`, so a change applies to the next alert without a restart. One
object serves both, so the two cannot disagree (as for `IBotAlertModes`).

@par Extension cases
  · a second quiet period (a weekend) is a list of choices where this holds one;
  · a quiet period per channel is a field here and a lookup in `QuietHoursHold`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import time

#: The machine's own clock, as the display time zone setting names it.
SYSTEM_ZONE = "SYSTEM"


@dataclass(frozen=True, slots=True)
class QuietHoursChoice:
    """`start` to `end` on the clock of `zone_key`, wrapping midnight when `start` is later
    than `end`. The zone is a name so the choice can be kept as text: `UTC`, an IANA name, or
    `SYSTEM` for the machine's own clock (`SYSTEM_ZONE`), which has no IANA name to store."""

    start: time
    end: time
    zone_key: str


class IQuietHoursSetting(ABC):
    @property
    @abstractmethod
    def read_only(self) -> bool:
        """Whether this copy of the app can keep a change (a second copy cannot)."""

    @abstractmethod
    def quiet_hours(self) -> QuietHoursChoice | None:
        """The quiet hours now; `None` when there are none."""

    @abstractmethod
    def set_quiet_hours(self, choice: QuietHoursChoice | None) -> None:
        """Sets and keeps the quiet hours; `None` removes them. Raises `OSError` when it cannot
        be kept, which includes a read-only copy: nothing is changed then."""
