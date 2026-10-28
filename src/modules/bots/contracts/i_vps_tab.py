"""`EPIC-047E` — port: what the VPS Bots tab is given to stand on, by the shell that owns the link.

@details The tab is the Bots screen's own classes (charter O4) on another backend, and the backend is these four things: the
screen's dispatcher (queries answered from the host's published facts, commands carried to the host's own gate), a candle feed
per venue (the host's candles, never the exchange's), the line above the tab, and the name of the host. The module defines the
port and the shell implements it over the link (`shell/vps_tab/`), because only the shell may hold the transport.

@par Extension cases
  · a second host at once - another `IVpsTab` behind a second route; nothing here names a host;
  · another thing the tab needs from the link - one more method here and one more in the shell's class.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_line import HostLine
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    ICandleFeed,
)


class IVpsTab(ABC):
    @abstractmethod
    def commands(self) -> ICommandDispatcher:
        """The screen's doors: `RemoteCommandDispatcher` over the link."""

    @abstractmethod
    def candle_feed(self, venue: TradingVenue) -> ICandleFeed:
        """`venue`'s candles, from the host."""

    @abstractmethod
    def host_line(self) -> HostLine:
        """The line above the tab now: host, keys, connected or not, the facts' age."""

    @abstractmethod
    def opened(self) -> None:
        """The tab was shown for the first time: the link starts now, never at boot (a run that never opens the tab
        makes no connection). Idempotent."""
