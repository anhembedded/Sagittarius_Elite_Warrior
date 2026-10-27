"""`BUG-224` - `bot stop` on the running host reaches the screen's Stop with a Futures bot.

The host's stop used to carry `ExposureHandling.KEEP` for every bot, and the screen's Stop refuses
KEEP on a position venue (`EPIC-039H`), so a Futures bot could never be stopped from the command
line. The collaborators here are the real ones - the operator handler, the host handler, the
screen's `StopBotCommandHandler` - behind a dispatcher that routes by command type, so the refusal
(or the close) is the one the host would answer.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
    StopBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot_for_host import (
    StopBotForHostCommandHandler,
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
    FakeBotClock,
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
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.test_bot_lifecycle_commands import (
    _RecordingRunner,
)

_SPOT_PORTS = FakeVenueTradingPorts(fake_venue_ports(TradingVenue.SPOT_TESTNET))
_ID = "abc123"
_CLOCK = FakeBotClock()
_OPEN = SessionReadyResult(
    ready=True, block_reason=None, reconciled_positions=(), reconciled_open_orders=()
)


class _RoutingDispatcher(ICommandDispatcher):
    """Hands each command to the handler of its type, as the application's dispatcher does."""

    def __init__(self) -> None:
        self.handlers: dict[type, ICommandHandler] = {}

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        return self.handlers[handler_class].execute(input_dto)


class _World:
    def __init__(self, venue: TradingVenue, *, session_open: bool = True) -> None:
        self.store = FakeBotStore()
        definition = BotDefinition("grid", "grid", venue, "BTCUSDT", {"lower": "1"})
        self.store.save(
            StoredBot(
                Bot(
                    BotId(_ID),
                    definition,
                    BotLifecycle(BotLifecycleState.RUNNING),
                    _CLOCK.now(),
                ),
                {},
            )
        )
        self.runner = _RecordingRunner(self.store, _CLOCK)
        self.session = FakeTradingSession()
        self.session.ready_answers(_OPEN)
        self.session.set_enabled(enabled=session_open)
        dispatcher = _RoutingDispatcher()
        dispatcher.handlers = {
            StopBotCommand: StopBotCommandHandler(self.store, self.runner, _SPOT_PORTS),
            StopBotForHostCommand: StopBotForHostCommandHandler(dispatcher),
        }
        self.handler = StopBotForOperatorCommandHandler(
            self.store,
            FakeVenueTradingPorts(
                fake_venue_ports(venue, trading_session=self.session)
            ),
            dispatcher,
        )

    def stop(self, *, close_position: bool = False) -> BotCommandResult:
        return self.handler.execute(
            StopBotForOperatorCommand(_ID, close_position=close_position)
        )


def test_a_futures_stop_with_close_position_closes_the_position_at_market() -> None:
    world = _World(TradingVenue.FUTURES_TESTNET)

    result = world.stop(close_position=True)

    assert result.accepted
    assert world.runner.sent == [("stop:CLOSE_AT_MARKET", _ID)]


def test_a_futures_stop_without_the_flag_is_refused_in_words_that_name_it() -> None:
    world = _World(TradingVenue.FUTURES_TESTNET, session_open=False)

    result = world.stop()

    assert result.refusal is BotRefusal.EXPOSURE_MUST_CLOSE
    assert "--close-position" in result.message
    assert "closes its position at market" in result.message
    assert world.runner.sent == []
    assert world.session.ready_requests == 0


def test_a_futures_close_opens_a_closed_session_first_as_the_stop_needs_it() -> None:
    world = _World(TradingVenue.FUTURES_TESTNET, session_open=False)

    result = world.stop(close_position=True)

    assert result.accepted
    assert world.session.ready_requests == 1
    assert world.runner.sent == [("stop:CLOSE_AT_MARKET", _ID)]


def test_a_spot_stop_without_the_flag_still_keeps_the_base() -> None:
    world = _World(TradingVenue.SPOT_TESTNET)

    result = world.stop()

    assert result.accepted
    assert world.runner.sent == [("stop:KEEP", _ID)]


def test_a_spot_stop_with_the_flag_sells_the_base_as_the_screens_close_does() -> None:
    world = _World(TradingVenue.SPOT_TESTNET)

    result = world.stop(close_position=True)

    assert result.accepted
    assert world.runner.sent == [("stop:CLOSE_AT_MARKET", _ID)]
