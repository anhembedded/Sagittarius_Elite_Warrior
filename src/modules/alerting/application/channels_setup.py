"""Switch the channels this run has on or off, from the Options page (`EPIC-036D8`).

A switched-off channel keeps its secret and its lane; the hub and the router skip it, so the
change applies to the next alert. Only a channel this run has can be switched: a switch for a
channel that is not running reaches nothing and would only look saved.

Switching every channel off is allowed and is the owner's word: `IAlertingStatus` then says no
channel carries alerts, the status bar says `Alerts: all channels off` (`ChannelHealth.enabled`,
`history_words.indicator_text`), and the Options page says so in its Channels note. The router's cover for a Critical (N8) chooses
among the enabled channels, so it never sends to one the owner switched off.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel_catalog import (
    IAlertChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_channel_enabling import (
    IChannelEnabling,
)

logger = logging.getLogger("App.Alerting")


class ChannelSwitch(Enum):
    TURNED_ON = "turned on"
    TURNED_OFF = "turned off"
    READ_ONLY = "read-only copy"
    UNKNOWN_CHANNEL = "channel not running"
    NOT_KEPT = "could not be kept"


@dataclass(frozen=True, slots=True)
class ChannelsState:
    #: The channels this run has, in the catalog's order.
    channels: tuple[str, ...]
    #: The ones switched off; every other channel is on.
    disabled: frozenset[str]
    #: `False` in a read-only copy, which cannot keep a change.
    editable: bool


class ChannelsSetup:
    def __init__(
        self, enabling: IChannelEnabling, catalog: IAlertChannelCatalog
    ) -> None:
        self._enabling = enabling
        self._catalog = catalog

    def state(self) -> ChannelsState:
        return ChannelsState(
            tuple(self._catalog.channel_ids()),
            self._enabling.disabled(),
            not self._enabling.read_only,
        )

    def turn_on(self, channel_id: str) -> ChannelSwitch:
        if (refused := self._refusal(channel_id)) is not None:
            return refused
        return self._kept(
            lambda: self._enabling.enable(channel_id), ChannelSwitch.TURNED_ON
        )

    def turn_off(self, channel_id: str) -> ChannelSwitch:
        if (refused := self._refusal(channel_id)) is not None:
            return refused
        return self._kept(
            lambda: self._enabling.disable(channel_id), ChannelSwitch.TURNED_OFF
        )

    def _refusal(self, channel_id: str) -> ChannelSwitch | None:
        if self._enabling.read_only:
            return self._told(ChannelSwitch.READ_ONLY)
        if channel_id not in self._catalog.channel_ids():
            return self._told(ChannelSwitch.UNKNOWN_CHANNEL)
        return None

    def _kept(self, keep: Callable[[], None], outcome: ChannelSwitch) -> ChannelSwitch:
        try:
            keep()
        except OSError as exc:
            logger.warning(
                "[alert-setup] a channel switch could not be kept (%s)",
                type(exc).__name__,
            )
            return self._told(ChannelSwitch.NOT_KEPT)
        return self._told(outcome)

    @staticmethod
    def _told(outcome: ChannelSwitch) -> ChannelSwitch:
        logger.info("[alert-setup] channels: %s", outcome.value)
        return outcome
