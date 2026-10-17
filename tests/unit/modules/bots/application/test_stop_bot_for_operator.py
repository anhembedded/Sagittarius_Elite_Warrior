"""`EPIC-038J` (owner's answer "B", 2026-10-17) - `bot stop` opens a closed order session, then Stops.

The host's own shutdown stop (`StopBotForHostCommand`) never opens a session; this one is a person's
deliberate action. Nothing is opened for a stop that would be refused, and a mainnet session is opened
only when the operator typed the venue.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot_for_operator import (
    StopBotForOperatorCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    StopBotForHostCommand,
    StopBotForOperatorCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FAKE_CLOCK_START,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_ready_result import (
    SessionBlockReason,
    SessionReadyResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

S = BotLifecycleState
_OPEN = SessionReadyResult(
    ready=True, block_reason=None, reconciled_positions=(), reconciled_open_orders=()
)
_REFUSED = SessionReadyResult(
    ready=False,
    block_reason=SessionBlockReason.UNEXPECTED_POSITIONS,
    reconciled_positions=(),
    reconciled_open_orders=(),
)


class _Dispatcher(ICommandDispatcher):
    def __init__(self) -> None:
        self.dispatched: list[object] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        assert isinstance(input_dto, handler_class)
        self.dispatched.append(input_dto)
        return BotCommandResult.done(getattr(input_dto, "bot_id"))  # noqa: B009 - the command names a bot


class _World:
    def __init__(
        self, venue: TradingVenue, state: S, *, session_open: bool = False
    ) -> None:
        self.session = FakeTradingSession()
        self.session.ready_answers(_OPEN)
        self.session.set_enabled(enabled=session_open)
        self.store = FakeBotStore()
        bot = Bot(
            BotId("aaaaaa"),
            BotDefinition("grid", "grid", venue, "BTCUSDT", {"lower": "1"}),
            BotLifecycle(state),
            FAKE_CLOCK_START,
        )
        self.store.save(StoredBot(bot, {}))
        self.dispatcher = _Dispatcher()
        self.handler = StopBotForOperatorCommandHandler(
            self.store,
            FakeVenueTradingPorts(
                fake_venue_ports(venue, trading_session=self.session)
            ),
            self.dispatcher,
        )

    def stop(self, confirmed: str | None = None) -> BotCommandResult:
        return self.handler.execute(StopBotForOperatorCommand("aaaaaa", confirmed))


def test_a_closed_testnet_session_is_opened_once_and_then_the_stop_is_the_hosts_keep_stop() -> (
    None
):
    world = _World(TradingVenue.SPOT_TESTNET, S.HALTED)

    result = world.stop()

    assert result.accepted
    assert world.session.ready_requests == 1
    assert world.dispatcher.dispatched == [StopBotForHostCommand("aaaaaa")]


def test_an_open_session_is_not_asked_again_and_mainnet_needs_no_answer_for_it() -> (
    None
):
    world = _World(TradingVenue.SPOT_MAINNET, S.HALTED, session_open=True)

    result = world.stop()

    assert result.accepted
    assert world.session.ready_requests == 0
    assert world.dispatcher.dispatched == [StopBotForHostCommand("aaaaaa")]


def test_a_closed_mainnet_session_is_opened_only_when_the_venue_was_typed() -> None:
    venue = TradingVenue.SPOT_MAINNET
    world = _World(venue, S.HALTED)

    refused = world.stop()
    wrong = world.stop(TradingVenue.SPOT_TESTNET.value)

    assert refused.refusal is wrong.refusal is BotRefusal.REAL_MONEY_NOT_CONFIRMED
    assert f"--confirm-venue {venue.value}" in refused.message
    assert world.session.ready_requests == 0
    assert world.dispatcher.dispatched == []
    assert world.stop(venue.value).accepted
    assert world.session.ready_requests == 1


def test_a_session_that_will_not_open_is_the_answer_and_nothing_is_stopped() -> None:
    world = _World(TradingVenue.SPOT_TESTNET, S.HALTED)
    world.session.ready_answers(_REFUSED)

    result = world.stop()

    assert not result.accepted
    assert result.refusal is BotRefusal.VENUE_NOT_READY
    assert world.dispatcher.dispatched == []


def test_a_stop_the_lifecycle_refuses_opens_nothing() -> None:
    world = _World(TradingVenue.SPOT_TESTNET, S.STOPPED)

    result = world.stop()

    assert result.refusal is BotRefusal.INVALID_TRANSITION
    assert world.session.ready_requests == 0
    assert world.dispatcher.dispatched == []


def test_a_position_venue_is_left_to_the_screens_refusal_and_opens_nothing() -> None:
    world = _World(TradingVenue.FUTURES_TESTNET, S.HALTED)

    world.stop()

    assert world.session.ready_requests == 0
    assert world.dispatcher.dispatched == [StopBotForHostCommand("aaaaaa")]


def test_a_bot_that_does_not_exist_is_refused() -> None:
    world = _World(TradingVenue.SPOT_TESTNET, S.HALTED)

    result = world.handler.execute(StopBotForOperatorCommand("zzzzzz"))

    assert result.refusal is BotRefusal.NOT_FOUND
    assert world.session.ready_requests == 0


def test_the_mainnet_refusal_names_the_other_recovering_bots_the_session_would_return() -> (
    None
):
    venue = TradingVenue.SPOT_MAINNET
    world = _World(venue, S.HALTED)
    for other, state in (
        ("bbbbbb", S.RECOVERING),
        ("cccccc", S.RECOVERING),
        ("dddddd", S.PAUSED),
    ):
        world.store.save(
            StoredBot(
                Bot(
                    BotId(other),
                    BotDefinition("grid", "grid", venue, "ETHUSDT", {"lower": "1"}),
                    BotLifecycle(state),
                    FAKE_CLOCK_START,
                ),
                {},
            )
        )

    refused = world.stop()

    assert refused.refusal is BotRefusal.REAL_MONEY_NOT_CONFIRMED
    assert "bbbbbb, cccccc" in refused.message and "dddddd" not in refused.message
    assert "before the restart" in refused.message
