"""`EPIC-047E` — the VPS tab's link to its host, kept for the life of the application.

@details One session per run: it reads the connection profile in use (`LinkProfiles.selected`, `EPIC-047D`), keeps a supervised
link to that host (`LinkSupervisor`: connect, notice a cut, reconnect by itself), holds the host's published picture
(`LinkHostWorld`), and offers the tab what it stands on (`IVpsTab`): the screen's dispatcher over the picture and the host's
own control door, a candle feed per venue, the line above the tab, and the tab's private bus for the events the link turns
into `BotChangedEvent` and `MarketTickEvent`.

It connects when the tab is first opened, never at boot, so a run that never opens the VPS tab makes no connection. G2: one host
at a time, the profile chosen when the tab opens; a change in Tools → Options → VPS Link takes effect at the next start of the
application (the tab says which profile it is on).

@par Extension cases
  · reconnecting to a profile changed at run time - a `restart` that stops the supervisor and starts it on the new profile;
    the picture and the bus stay.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import LinkProfile
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_line import HostLine
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_vps_tab import IVpsTab
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.remote_host_ports import (
    RemoteHostPorts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.module import remote_bots_dispatcher
from Sagittarius_Elite_Warrior.src.shell.link_version import link_app_version
from Sagittarius_Elite_Warrior.src.shell.vps_link.host_candle_feed import (
    HostCandleFeed,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.host_event_publisher import (
    HostEventPublisher,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.host_state_line import (
    host_state_line,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.link_host_control import (
    LinkHostControl,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.link_host_world import LinkHostWorld
from Sagittarius_Elite_Warrior.src.shell.vps_link.unanswered_ledger import (
    UnansweredLedger,
)
from Sagittarius_Elite_Warrior.src.shell.wire_roots import link_roots
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    ICandleFeed,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.link_profiles import (
    LinkProfiles,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.link_supervisor import (
    LinkSupervisor,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.transport_registry import (
    TransportRegistry,
)
from Sagittarius_Elite_Warrior.src.support.wire.link_handshake import hello_of
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_event_bus import IEventBus

logger = logging.getLogger("App.VpsTab")

NO_PROFILE_WORDS = "No VPS connection is chosen: add one in Tools → Options → VPS Link, then restart the application."


class VpsTabSession(IVpsTab):
    def __init__(
        self,
        profiles: LinkProfiles,
        transports: TransportRegistry,
        local: ICommandDispatcher,
        kinds: IBotKindCatalog,
    ) -> None:
        self._profiles = profiles
        self._transports = transports
        self._roots = link_roots()
        self._bus = MemoryEventBus()
        self._world = LinkHostWorld(self._roots, HostEventPublisher(self._bus))
        self._ledger = UnansweredLedger()
        ports = RemoteHostPorts(
            self._world,
            LinkHostControl(self._world, self._roots, self._ledger),
            self._ledger,
            local,
        )
        self._dispatcher = remote_bots_dispatcher(ports, kinds)
        self._feeds: dict[TradingVenue, HostCandleFeed] = {}
        self._profile: LinkProfile | None = None
        self._supervisor: LinkSupervisor | None = None

    @property
    def events(self) -> IEventBus:
        """The tab's private bus: the link's events, heard by the tab's feeds and by nothing else."""
        return self._bus

    def start(self) -> None:
        """Connects the chosen profile, once. Without a profile nothing connects and the line says why."""
        if self._supervisor is not None:
            return
        self._profile = self._profiles.selected()
        if self._profile is None:
            logger.info("[vps-tab] no connection profile is chosen; nothing to connect")
            return
        self._supervisor = LinkSupervisor(
            self._profile,
            self._transports,
            hello_of(self._roots, link_app_version()),
            self._world,
        )
        self._supervisor.start()
        logger.info("[vps-tab] connecting profile %s", self._profile.name)

    def stop(self) -> None:
        supervisor, self._supervisor = self._supervisor, None
        if supervisor is not None:
            supervisor.stop()

    # -- IVpsTab ----------------------------------------------------------------------------

    def commands(self) -> ICommandDispatcher:
        return self._dispatcher

    def candle_feed(self, venue: TradingVenue) -> ICandleFeed:
        if venue not in self._feeds:
            self._feeds[venue] = HostCandleFeed(venue, self._world, self._roots)
        return self._feeds[venue]

    def opened(self) -> None:
        self.start()

    def host_line(self) -> HostLine:
        if self._profile is None:
            return HostLine(NO_PROFILE_WORDS, False)
        return host_state_line(
            self._profile.name,
            self._world.current(),
            self._world.status,
            datetime.now(UTC),
        )
