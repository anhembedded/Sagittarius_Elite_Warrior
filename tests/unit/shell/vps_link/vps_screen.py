"""`EPIC-047E` - the Bots screen on the VPS host, as the tests open it: the real classes over the real bridge session."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_line import HostLine
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_vps_tab import IVpsTab
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_dependencies import (
    BotsBackend,
    backend_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.vps_command_ids import (
    vps_commands,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.host_candle_feed import (
    HostCandleFeed,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.host_state_line import (
    host_state_line,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    ICandleFeed,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_status import (
    LinkState,
    LinkStatus,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.bots_screen.bots_screen_fixtures import (
    Answers,
    BotsScreen,
    open_screen,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.dispatcher_world import (
    build_dispatcher,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.vps_world import VpsTabWorld
from Sagittarius_Elite_Warrior.tests.unit.support.wire.bridge.bridge_world import ROOTS
from sagittarius_engine.interfaces.i_container import IContainer

VPS_ROUTE = "vps_bots"


class TabOnTheWorld(IVpsTab):
    """The shell's `IVpsTab` without its link: the same doors over a running `VpsTabWorld`."""

    def __init__(self, tab: VpsTabWorld, local: ICommandDispatcher) -> None:
        self._tab = tab
        self._dispatcher = build_dispatcher(tab, local)[0]
        self.opened_count = 0

    def commands(self) -> ICommandDispatcher:
        return self._dispatcher

    def candle_feed(self, venue: TradingVenue) -> ICandleFeed:
        return HostCandleFeed(venue, self._tab.world, ROOTS)

    def host_line(self) -> HostLine:
        return host_state_line(
            "nathan-warrior",
            self._tab.world.current(),
            LinkStatus(LinkState.CONNECTED, "connected"),
            datetime.now(UTC),
        )

    def opened(self) -> None:
        self.opened_count += 1


class VpsScreen:
    def __init__(
        self, screen: BotsScreen, actions: Any, tab: TabOnTheWorld, backend: BotsBackend
    ) -> None:
        self.backend = backend
        self.screen = screen
        self.actions = actions
        self.tab = tab


def open_vps_screen(
    tmp_path: Path, qtbot: Any, tab: VpsTabWorld, answers: Answers | None = None
) -> VpsScreen:
    """The Bots screen as the shell builds the VPS tab: `BotsPresenter` with the backend `backend_for` gives a container
    carrying an `IVpsTab`, and the commands bound under the tab's ids."""
    holder: list[TabOnTheWorld] = []
    backends: list[BotsBackend] = []

    def backend_of(container: IContainer) -> BotsBackend:
        """The shell's way: the tab's session sits in the container and `backend_for` chooses the VPS backend."""
        on_world = TabOnTheWorld(tab, container.resolve(ICommandDispatcher))
        holder.append(on_world)
        container.singleton(IVpsTab, on_world)
        backends.append(backend_for(container))
        return backends[0]

    screen = open_screen(
        tmp_path,
        qtbot,
        answers=answers,
        backend_of=backend_of,
        commands_of=vps_commands,
        route=VPS_ROUTE,
    )
    return VpsScreen(screen, screen.actions, holder[0], backends[0])
