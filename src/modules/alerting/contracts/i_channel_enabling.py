"""`IChannelEnabling` — which channels the owner has switched off (`EPIC-036D8`).

The Options page edits through this port; the hub reads the result as
`AlertSettings.disabled_channels` through `IAlertSettingsSource`, so a change applies to the next
alert without a restart. One object serves both, so the two cannot disagree (as for
`IAlertRouting`).

A disabled channel keeps its secret and its lane: the hub and the router skip it, and
`IAlertingStatus` counts it as not carrying alerts. Switching it on again needs nothing but this
call.

@par Extension cases
  · a reason or a "until" time for a pause is one more field beside the id in the file and one
    more argument here;
  · a channel switched off for one group only is a route set to Off, which already exists.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IChannelEnabling(ABC):
    @property
    @abstractmethod
    def read_only(self) -> bool:
        """Whether this copy of the app can keep a change (a second copy cannot)."""

    @abstractmethod
    def disabled(self) -> frozenset[str]:
        """The ids of the channels switched off; every other channel is on."""

    @abstractmethod
    def disable(self, channel_id: str) -> None:
        """Switches a channel off and keeps it. Raises `OSError` when it cannot be kept, which
        includes a read-only copy: nothing is changed then."""

    @abstractmethod
    def enable(self, channel_id: str) -> None:
        """Switches a channel on again and keeps it; the same failure as `disable`."""
