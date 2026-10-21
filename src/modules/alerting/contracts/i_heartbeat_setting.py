"""`IHeartbeatSetting` — how often the heartbeat is sent (`EPIC-036D9`).

The Options page edits through this port; the heartbeat reads the result as
`AlertSettings.heartbeat_every` through `IAlertSettingsSource` on every pass, so a change applies
without a restart. One object serves both, so the two cannot disagree (as for `IQuietHoursSetting`).

@par Extension cases
  · the hour of the daily summary is one more setting beside this one, read the same way;
  · turning the heartbeat off is a `None` that means "never" where today it means "the default".
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IHeartbeatSetting(ABC):
    @property
    @abstractmethod
    def read_only(self) -> bool:
        """Whether this copy of the app can keep a change (a second copy cannot)."""

    @abstractmethod
    def heartbeat_hours(self) -> int | None:
        """The interval the owner chose, in whole hours; `None` when none was chosen (the
        policy's own applies)."""

    @abstractmethod
    def set_heartbeat_hours(self, hours: int | None) -> None:
        """Sets and keeps the interval; `None` puts it back to the default. Raises `OSError` when
        it cannot be kept, which includes a read-only copy: nothing is changed then."""
