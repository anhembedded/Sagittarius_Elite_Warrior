"""`IAlertRouting` — the routing matrix the owner edits (`EPIC-036D7`).

The Options page edits through this port; the hub reads the result as `AlertSettings.routes`
through `IAlertSettingsSource`, so a change applies to the next alert without a restart. One
object serves both, so the two cannot disagree (as for `IBotAlertModes`).

A cell is one `(group, channel)` pair. A cell with no route is its default (`AlertSettings.
loudness_for`: CRITICAL loud, the rest silent). `AlertRouter` keeps its own cover for a CRITICAL:
whatever the matrix says, one that fewer than two channels would hear is lifted to two (N8).

@par Extension cases
  · a per-severity cell is one more field on `AlertRoute` and one more lookup in `loudness_for`;
  · a route per bot is a bot id on `AlertRoute`, read before the group's.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_group import AlertGroup
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_route import AlertRoute
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness


class IAlertRouting(ABC):
    @property
    @abstractmethod
    def read_only(self) -> bool:
        """Whether this copy of the app can keep a change (a second copy cannot)."""

    @abstractmethod
    def routes(self) -> tuple[AlertRoute, ...]:
        """The cells the owner set; a cell not in it is its default."""

    @abstractmethod
    def set_route(
        self, group: AlertGroup, channel_id: str, loudness: Loudness | None
    ) -> None:
        """Sets and keeps one cell; `None` puts it back to its default. Raises `OSError` when it
        cannot be kept, which includes a read-only copy: nothing is changed then."""
