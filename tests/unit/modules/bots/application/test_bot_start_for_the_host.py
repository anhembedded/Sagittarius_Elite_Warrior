"""`EPIC-038K` - `bot start` on the running host runs the screen's own Start.

The collaborators are the real ones - the host handlers, the screen's `StartBotCommandHandler` with
its readiness reader - behind a dispatcher that routes by
command type, as the application's does, so a refusal is the one the host would put in the audit.
Only the runner (what actually starts the bot's worker) is a recording double. A Futures start runs
the same handlers and is proven on the composed app, over the Futures fake exchange, in
`tests/integration/modules/bots/test_bot_start_on_the_running_host_on_the_fake_exchange.py`;
here a Futures mainnet bot proves the venue question, which does not depend on the venue's account.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_command_lock import (
    BotCommandLock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
    StartBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot_for_host import (
    StartBotForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    StartBotForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RESUME_PROPOSES_STATES,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.venue_bot_cap import (
    MAX_ACTIVE_BOTS_PER_VENUE,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.readiness_world import (
    ReadinessWorld,
    add_bot,
    readiness_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    SYMBOL,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.test_start_bot_real_money import (
    _CountingRunner,
)

S = BotLifecycleState
V = TradingVenue
_OTHER_SYMBOLS = ("ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT")


class _RoutingDispatcher(ICommandDispatcher):
    """Hands each command to the handler of its type, as the application's dispatcher does."""

    def __init__(self) -> None:
        self.handlers: dict[type, ICommandHandler] = {}

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        return self.handlers[handler_class].execute(input_dto)


class _Host:
    """The host-side handlers over a readiness world, with a runner that records the starts."""

    def __init__(self, world: ReadinessWorld) -> None:
        self.world = world
        self.runner = _CountingRunner()
        dispatcher = _RoutingDispatcher()
        dispatcher.handlers = {
            StartBotCommand: StartBotCommandHandler(
                world.store, self.runner, BotCommandLock(), world.reader, world.clock
            ),
        }
        self._start = StartBotForHostCommandHandler(world.store, dispatcher)

    def start(self, confirmed_venue: str | None = None) -> BotCommandResult:
        return self._start.execute(StartBotForHostCommand(BOT, confirmed_venue))

    def state_of_the_bot(self) -> BotLifecycleState:
        return self.world.store.load(BotId(BOT)).bot.state


def _host(
    state: BotLifecycleState = S.DRAFT, venue: TradingVenue = V.SPOT_TESTNET
) -> _Host:
    world = readiness_world(bot_venue=venue)
    add_bot(world, BOT, state, venue=venue, symbol=SYMBOL)
    return _Host(world)


# ---- start -------------------------------------------------------------------------------------


@pytest.mark.parametrize("state", [S.DRAFT, S.STOPPED])
def test_a_bot_at_rest_is_started_once_by_the_screens_start(
    state: BotLifecycleState,
) -> None:
    host = _host(state)

    result = host.start()

    assert result.accepted, result.message
    assert host.runner.started == [BOT]


@pytest.mark.parametrize("state", [s for s in S if s not in (S.DRAFT, S.STOPPED)])
def test_a_bot_that_is_not_at_rest_is_never_started_and_nothing_is_opened(
    state: BotLifecycleState,
) -> None:
    host = _host(state)

    result = host.start()

    assert not result.accepted
    assert result.refusal is BotRefusal.INVALID_TRANSITION
    assert host.runner.started == []
    assert host.world.session.ready_requests == 0
    assert host.state_of_the_bot() is state


@pytest.mark.parametrize("state", sorted(RESUME_PROPOSES_STATES, key=lambda s: s.value))
def test_a_halted_or_awaiting_bot_is_refused_with_the_way_back_in_words(
    state: BotLifecycleState,
) -> None:
    host = _host(state)

    result = host.start()

    assert result.refusal is BotRefusal.INVALID_TRANSITION
    assert state.value in result.message
    assert "run --resume-halted" in result.message and "Bots tab" in result.message
    assert host.runner.started == []


def test_the_state_is_judged_before_the_money_question_for_a_halted_mainnet_bot() -> (
    None
):
    host = _host(S.HALTED, V.SPOT_MAINNET)

    result = host.start()

    assert result.refusal is BotRefusal.INVALID_TRANSITION
    assert "--confirm-venue" not in result.message


@pytest.mark.parametrize("venue", [V.SPOT_MAINNET, V.FUTURES_MAINNET])
def test_a_mainnet_start_without_the_venue_typed_opens_and_starts_nothing(
    venue: TradingVenue,
) -> None:
    host = _host(S.STOPPED, venue)

    result = host.start()

    assert result.refusal is BotRefusal.REAL_MONEY_NOT_CONFIRMED
    assert f"--confirm-venue {venue.value}" in result.message
    assert "RECOVERING" not in result.message
    assert host.runner.started == []
    assert host.world.session.ready_requests == 0


def test_a_mainnet_start_with_another_venues_name_typed_is_refused() -> None:
    host = _host(S.STOPPED, V.SPOT_MAINNET)

    result = host.start(V.FUTURES_MAINNET.value)

    assert result.refusal is BotRefusal.REAL_MONEY_NOT_CONFIRMED
    assert host.runner.started == []


def test_the_refusal_for_a_mainnet_venue_names_the_other_bots_the_open_would_reconcile() -> (
    None
):
    host = _host(S.STOPPED, V.SPOT_MAINNET)
    add_bot(
        host.world,
        "rec001",
        S.RECOVERING,
        venue=V.SPOT_MAINNET,
        symbol=_OTHER_SYMBOLS[0],
    )
    add_bot(
        host.world,
        "rec002",
        S.RECOVERING,
        venue=V.SPOT_MAINNET,
        symbol=_OTHER_SYMBOLS[1],
    )
    add_bot(
        host.world,
        "run003",
        S.RUNNING,
        venue=V.SPOT_MAINNET,
        symbol=_OTHER_SYMBOLS[2],
    )

    result = host.start()

    assert result.refusal is BotRefusal.REAL_MONEY_NOT_CONFIRMED
    assert "rec001, rec002" in result.message
    assert "run003" not in result.message
    assert "--confirm-venue spot_mainnet" in result.message


def test_the_recovering_bots_of_another_venue_are_not_named() -> None:
    host = _host(S.STOPPED, V.SPOT_MAINNET)
    add_bot(
        host.world,
        "rec001",
        S.RECOVERING,
        venue=V.SPOT_TESTNET,
        symbol=_OTHER_SYMBOLS[0],
    )

    result = host.start()

    assert "rec001" not in result.message


def test_with_the_venue_typed_a_waiting_recovering_bot_still_refuses_the_start_in_words() -> (
    None
):
    host = _host(S.STOPPED, V.SPOT_MAINNET)
    add_bot(
        host.world,
        "rec001",
        S.RECOVERING,
        venue=V.SPOT_MAINNET,
        symbol=_OTHER_SYMBOLS[0],
    )

    result = host.start("spot_mainnet")

    # The readiness lists everything left, the waiting bot among it; this unit world has no
    # mainnet key, so the venue's own item comes first - the composed app proves the order.
    assert not result.accepted
    assert "waiting to recover (rec001)" in result.message
    assert host.runner.started == []
    assert host.world.session.ready_requests == 0


def test_a_start_on_a_symbol_another_bot_holds_is_refused_in_words() -> None:
    host = _host(S.STOPPED)
    add_bot(host.world, "hol001", S.HALTED, symbol=SYMBOL)

    result = host.start()

    assert result.refusal is BotRefusal.ONE_ACTIVE_BOT_PER_SYMBOL
    assert "hol001" in result.message
    assert host.runner.started == []


def test_a_start_on_a_full_venue_is_refused_in_words_at_the_cap_and_not_below_it() -> (
    None
):
    host = _host(S.STOPPED)
    for index in range(MAX_ACTIVE_BOTS_PER_VENUE - 1):
        add_bot(host.world, f"run00{index}", S.RUNNING, symbol=_OTHER_SYMBOLS[index])
    assert host.start().accepted, "one below the cap starts"
    host.runner.started.clear()

    add_bot(
        host.world,
        "run00x",
        S.RUNNING,
        symbol=_OTHER_SYMBOLS[MAX_ACTIVE_BOTS_PER_VENUE - 1],
    )
    result = host.start()

    assert result.refusal is BotRefusal.VENUE_FULL
    assert host.runner.started == []


def test_starting_one_bot_leaves_every_other_bot_as_it_was() -> None:
    host = _host(S.STOPPED)
    add_bot(host.world, "run001", S.RUNNING, symbol=_OTHER_SYMBOLS[0])
    add_bot(host.world, "pau002", S.PAUSED, symbol=_OTHER_SYMBOLS[1])

    assert host.start().accepted

    assert host.runner.started == [BOT]
    assert host.world.store.load(BotId("run001")).bot.state is S.RUNNING
    assert host.world.store.load(BotId("pau002")).bot.state is S.PAUSED


def test_a_start_for_a_bot_that_does_not_exist_is_refused() -> None:
    host = _host()

    result = _Host(host.world)._start.execute(StartBotForHostCommand("nobody"))

    assert result.refusal is BotRefusal.NOT_FOUND
