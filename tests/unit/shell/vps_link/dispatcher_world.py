"""`EPIC-047E` - what the remote dispatcher's tests share: the Bots screen's dispatcher over a running world."""

from __future__ import annotations

import threading

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlReply,
    HostControlRequest,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.remote_host.remote_command_dispatcher import (
    RemoteCommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.remote_host.remote_queries import (
    RemoteQueries,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.remote_host_ports import (
    RemoteHostPorts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import GridKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.vps_world import (
    VpsTabWorld,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.bridge.bridge_world import (
    FakeDoor,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_bots import (
    full_bot,
    minimal_bot,
)

BTC = full_bot()  # b-0001, a Futures Testnet bot
ETH = minimal_bot()  # b-0002, a Spot Testnet draft
LOCAL_ANSWER = object()


class _Local(ICommandDispatcher):
    """The screen's own dispatcher, which answers the pure assessment."""

    def __init__(self) -> None:
        self.asked: list[type] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        self.asked.append(handler_class)
        return LOCAL_ANSWER


class BlockingDoor(FakeDoor):
    """A host door that holds a command until the test releases it."""

    def __init__(self) -> None:
        super().__init__()
        self.arrived = threading.Event()
        self.release = threading.Event()

    def send(
        self, request_id: str, request: HostControlRequest, wait_s: float
    ) -> HostControlReply:
        self.sent.append((request_id, request, wait_s))
        self.arrived.set()
        self.release.wait(timeout=10)
        return self.reply


def build_dispatcher(
    tab: VpsTabWorld, local: ICommandDispatcher | None = None
) -> tuple[RemoteCommandDispatcher, ICommandDispatcher]:
    local = local or _Local()
    kinds = BotKindCatalog([GridKind(None, GridThresholds())])  # type: ignore[arg-type]
    ports = RemoteHostPorts(tab.world, tab.control, tab.unanswered, local)
    return RemoteCommandDispatcher(ports, RemoteQueries(kinds)), local


def ask(dispatcher: RemoteCommandDispatcher, query: object) -> object:
    return dispatcher.dispatch(type(query), query)
