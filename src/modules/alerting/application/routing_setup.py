"""Set the routing matrix the Options page edits (`EPIC-036D7`).

A cell is `(group, channel)`: how that kind of alert sounds on that channel. A cell the owner has
not set is its default (`AlertSettings.loudness_for`), and putting a cell back is `None`, not a
copy of the default, so a later change of the defaults reaches an owner who never chose.

Only a channel this run has can be set: a route for a channel that is not running reaches nothing
and would only look saved. `AlertRouter` keeps its own cover whatever the matrix says: a CRITICAL
that fewer than two channels would hear is lifted to two (N8), so Off in every cell of a group
never silences a halt.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel_catalog import (
    IAlertChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_routing import (
    IAlertRouting,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_group import AlertGroup
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness

logger = logging.getLogger("App.Alerting")


class RouteSave(Enum):
    SAVED = "saved"
    BACK_TO_DEFAULT = "back to the default"
    READ_ONLY = "read-only copy"
    UNKNOWN_CHANNEL = "channel not running"
    NOT_KEPT = "could not be kept"


@dataclass(frozen=True, slots=True)
class RoutingState:
    #: The channels this run has, in the catalog's order: the matrix's columns.
    channels: tuple[str, ...]
    #: What the owner set; a cell not in it is its default.
    chosen: dict[tuple[AlertGroup, str], Loudness]
    #: `False` in a read-only copy, which cannot keep a change.
    editable: bool


class RoutingSetup:
    def __init__(self, routing: IAlertRouting, catalog: IAlertChannelCatalog) -> None:
        self._routing = routing
        self._catalog = catalog

    def state(self) -> RoutingState:
        return RoutingState(
            tuple(self._catalog.channel_ids()),
            {
                (route.group, route.channel_id): route.loudness
                for route in self._routing.routes()
            },
            not self._routing.read_only,
        )

    def set_cell(
        self, group: AlertGroup, channel_id: str, loudness: Loudness | None
    ) -> RouteSave:
        if self._routing.read_only:
            return self._told(RouteSave.READ_ONLY)
        if channel_id not in self._catalog.channel_ids():
            return self._told(RouteSave.UNKNOWN_CHANNEL)
        try:
            self._routing.set_route(group, channel_id, loudness)
        except OSError as exc:
            logger.warning(
                "[alert-setup] a route could not be kept (%s)", type(exc).__name__
            )
            return self._told(RouteSave.NOT_KEPT)
        return self._told(
            RouteSave.BACK_TO_DEFAULT if loudness is None else RouteSave.SAVED
        )

    @staticmethod
    def _told(outcome: RouteSave) -> RouteSave:
        logger.info("[alert-setup] routing: %s", outcome.value)
        return outcome
