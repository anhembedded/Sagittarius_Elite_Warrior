"""`BUG-274` - a person's Stop opens a closed order session before it is queued; an automated one never does.

@details The Bots screen's Stop on a HALTED bot after a restart: the session is closed, so the stop's
budget registration was refused and the bot waited in STOPPING for a session nobody opened. Resume,
Start and the headless `bot stop` open it; the Stop that carries the person's answer to the
real-money question now does too, passing the venue's position claims as they do (`BUG-250`). A Stop
with no answer (the loss cap, the host's shutdown policy) opens nothing.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
    StopBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
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
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.test_bot_lifecycle_commands import (
    _RecordingRunner,
)

_ID = "abc123"
_CLOCK = FakeBotClock()
_OPEN = SessionReadyResult(
    ready=True, block_reason=None, reconciled_positions=(), reconciled_open_orders=()
)
_CLOSED = SessionReadyResult(
    ready=False,
    block_reason=SessionBlockReason.UNEXPECTED_POSITIONS,
    reconciled_positions=(),
    reconciled_open_orders=(),
)


class _World:
    def __init__(
        self,
        venue: TradingVenue,
        state: BotLifecycleState,
        *,
        session_open: bool,
        opens: bool = True,
    ) -> None:
        self.store = FakeBotStore()
        self.store.save(
            StoredBot(
                Bot(
                    BotId(_ID),
                    BotDefinition("grid", "grid", venue, "BTCUSDT", {"lower": "1"}),
                    BotLifecycle(state),
                    _CLOCK.now(),
                ),
                {},
            )
        )
        self.runner = _RecordingRunner(self.store, _CLOCK)
        self.session = FakeTradingSession()
        self.session.ready_answers(_OPEN if opens else _CLOSED)
        self.session.set_enabled(enabled=session_open)
        self.handler = StopBotCommandHandler(
            self.store,
            self.runner,
            FakeVenueTradingPorts(
                fake_venue_ports(venue, trading_session=self.session)
            ),
        )

    def stop(self, *, by_person: bool) -> BotCommandResult:
        return self.handler.execute(
            StopBotCommand(
                _ID, ExposureHandling.CLOSE_AT_MARKET, real_money_confirmed=by_person
            )
        )


@pytest.mark.parametrize(
    "venue",
    [TradingVenue.SPOT_TESTNET, TradingVenue.FUTURES_TESTNET],
    ids=["spot", "futures"],
)
@pytest.mark.parametrize(
    "state",
    [BotLifecycleState.HALTED, BotLifecycleState.RECOVERING, BotLifecycleState.ERROR],
)
def test_a_persons_stop_opens_the_closed_session_then_is_queued(
    venue: TradingVenue, state: BotLifecycleState
) -> None:
    world = _World(venue, state, session_open=False)

    result = world.stop(by_person=True)

    assert result.accepted
    assert world.session.ready_requests == 1
    assert world.runner.sent == [("stop:CLOSE_AT_MARKET", _ID)]


def test_an_automated_stop_opens_nothing_and_is_still_queued() -> None:
    world = _World(
        TradingVenue.FUTURES_TESTNET, BotLifecycleState.HALTED, session_open=False
    )

    result = world.stop(by_person=False)

    assert result.accepted
    assert world.session.ready_requests == 0
    assert world.runner.sent == [("stop:CLOSE_AT_MARKET", _ID)]


def test_an_open_session_is_not_asked_again() -> None:
    world = _World(
        TradingVenue.FUTURES_TESTNET, BotLifecycleState.HALTED, session_open=True
    )

    world.stop(by_person=True)

    assert world.session.ready_requests == 0
    assert world.runner.sent == [("stop:CLOSE_AT_MARKET", _ID)]


def test_a_session_that_will_not_open_refuses_the_stop_in_its_words_and_queues_nothing() -> (
    None
):
    world = _World(
        TradingVenue.FUTURES_TESTNET,
        BotLifecycleState.HALTED,
        session_open=False,
        opens=False,
    )

    result = world.stop(by_person=True)

    assert result.refusal is BotRefusal.VENUE_NOT_READY
    assert "unexpected open positions" in result.message
    assert world.runner.sent == []
