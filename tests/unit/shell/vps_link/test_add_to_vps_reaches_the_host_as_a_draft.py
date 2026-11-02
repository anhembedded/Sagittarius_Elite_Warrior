"""`EPIC-047E` (Add to VPS, charter Scenario 2) - a bot designed here reaches the host's own door as its `add` verb, over the real bridge.

The business promise: the handler turns a stored bot into the host's `add` request; the request crosses the real wire and the host's
door receives exactly that entry (name, kind, venue, symbol, parameters) with no real-money confirmation, because an add places no
order; the reply is the host's. A bot that no longer exists sends nothing. A link that is not up sends nothing and says so.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    ADD_SUBJECT,
    HostControlAction,
    HostControlReply,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_document import (
    BotPlanDocument,
    PlannedBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_export import (
    UnknownBotsError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.add_bot_to_vps import (
    AddBotToVpsCommand,
    AddBotToVpsCommandHandler,
    AddedToVps,
    NotAddedToVps,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    DesiredState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_vps_delivery import (
    IVpsDelivery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import GridKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.shell.vps_tab.shared_vps_session import (
    SharedVpsSession,
)
from Sagittarius_Elite_Warrior.src.shell.vps_tab.vps_delivery import VpsDelivery
from Sagittarius_Elite_Warrior.src.shell.vps_tab.vps_link_binding import bind_vps_link
from Sagittarius_Elite_Warrior.src.shell.vps_tab.vps_tab_session import (
    NO_PROFILE_WORDS,
    VpsTabSession,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.link_profiles import (
    LinkProfiles,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.transport_registry import (
    TransportRegistry,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.vps_world import VpsTabWorld
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer

_PLANNED = PlannedBot(
    "mean reverter",
    "grid",
    TradingVenue.FUTURES_TESTNET,
    "ETHUSDT",
    DesiredState.RUNNING,
    {"levels": "12", "lower": "1500"},
)


class _Stored(ICommandDispatcher):
    """The local application's answer to the plan query: the one bot, or none."""

    def __init__(self, exists: bool = True) -> None:
        self._exists = exists

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        if not self._exists:
            raise UnknownBotsError(("a00001",))
        return BotPlanDocument((_PLANNED,))


class _OverTheLink(IVpsDelivery):
    """The delivery the shell builds, with the test world's control behind it."""

    def __init__(self, tab: VpsTabWorld) -> None:
        self._tab = tab

    def send(self, request: HostControlRequest, wait_s: float) -> HostControlReply:
        return self._tab.control.send(request, wait_s)


def test_the_hosts_door_receives_the_bot_as_an_add_with_no_real_money_confirmation(
    tab: VpsTabWorld,
) -> None:
    tab.host.door.reply = HostControlReply(
        HostControlStatus.DONE, "bot ab12cd was added as a DRAFT", "c" * 32, "ab12cd"
    )

    result = AddBotToVpsCommandHandler(_Stored(), _OverTheLink(tab)).execute(
        AddBotToVpsCommand("a00001")
    )

    ((_, request, _),) = tab.host.door.sent
    assert request.action is HostControlAction.ADD
    assert request.bot_id == ADD_SUBJECT
    assert request.confirmed_venue is None
    assert request.entry is not None
    assert (
        request.entry.name,
        request.entry.kind,
        request.entry.venue,
        request.entry.symbol,
    ) == ("mean reverter", "grid", "futures_testnet", "ETHUSDT")
    assert {(p.key, p.value) for p in request.entry.params} == {
        ("levels", "12"),
        ("lower", "1500"),
    }
    assert result == AddedToVps(
        "mean reverter", "ab12cd", "bot ab12cd was added as a DRAFT"
    )


def test_the_host_refusing_is_the_answer_and_nothing_is_called_added(
    tab: VpsTabWorld,
) -> None:
    tab.host.door.reply = HostControlReply(
        HostControlStatus.REFUSED, "a bot named mean reverter already exists", "d" * 32
    )

    result = AddBotToVpsCommandHandler(_Stored(), _OverTheLink(tab)).execute(
        AddBotToVpsCommand("a00001")
    )

    assert result == NotAddedToVps(
        "mean reverter", "a bot named mean reverter already exists"
    )


def test_a_bot_that_no_longer_exists_sends_nothing(tab: VpsTabWorld) -> None:
    result = AddBotToVpsCommandHandler(
        _Stored(exists=False), _OverTheLink(tab)
    ).execute(AddBotToVpsCommand("a00001"))

    assert isinstance(result, NotAddedToVps)
    assert not result.unknown
    assert tab.host.door.sent == []


def test_a_link_that_is_not_up_sends_nothing_and_a_missing_profile_is_said() -> None:

    kinds = BotKindCatalog([GridKind(None, GridThresholds())])  # type: ignore[arg-type]
    session = VpsTabSession(
        LinkProfiles(), TransportRegistry(), _Stored(), kinds, print
    )
    request = HostControlRequest(HostControlAction.ADD, ADD_SUBJECT)

    reply = session.deliver(request, 1.0)

    assert reply.status is HostControlStatus.NOT_RUNNING
    assert "nothing was sent" in reply.message
    assert session.host_line().text == NO_PROFILE_WORDS
    session.stop()


def test_the_delivery_and_the_tab_share_one_session() -> None:

    container = StdLibContainer()
    bind_vps_link(container)

    shared = container.resolve(SharedVpsSession)

    assert isinstance(container.resolve(IVpsDelivery), VpsDelivery)
    assert container.resolve(SharedVpsSession) is shared
