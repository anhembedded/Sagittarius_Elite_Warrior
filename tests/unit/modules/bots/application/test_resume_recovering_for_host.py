"""`run --resume-recovering`: each RECOVERING bot gets its own Resume (`EPIC-038D`, decision O2, `BOT-183`).

A restart leaves RUNNING and PAUSED bots RECOVERING until a person resumes them. The host's request
is the screen's own `ResumeBotCommand` for every RECOVERING bot of a venue, so it no longer depends on
the switch-on event a session opening publishes (an already open session publishes none, and an
opening names the bot it was for): the bot's Resume opens the session for it and reconciles it. A
mainnet venue is resumed only when the operator typed it, and one bot's refusal leaves the others
resumed.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_recovering_for_host import (
    ResumeRecoveringForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    ResumeRecoveringForHostCommand,
    ResumeRecoveringResult,
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

SPOT_TESTNET = TradingVenue.SPOT_TESTNET
FUTURES_TESTNET = TradingVenue.FUTURES_TESTNET
SPOT_MAINNET = TradingVenue.SPOT_MAINNET

_OPEN = SessionReadyResult(
    ready=True, block_reason=None, reconciled_positions=(), reconciled_open_orders=()
)
_REFUSED = SessionReadyResult(
    ready=False,
    block_reason=SessionBlockReason.UNEXPECTED_POSITIONS,
    reconciled_positions=(),
    reconciled_open_orders=(),
)


def _bot(
    store: FakeBotStore, bot_id: str, venue: TradingVenue, state: BotLifecycleState
) -> None:
    bot = Bot(
        BotId(bot_id),
        BotDefinition("grid", "grid", venue, "BTCUSDT", {"lower": "1"}),
        BotLifecycle(state),
        FAKE_CLOCK_START,
    )
    store.save(StoredBot(bot, {}))


class _Dispatcher(ICommandDispatcher):
    """Answers the screen's Resume as the command handler would: done, or the refusal a test sets."""

    def __init__(self) -> None:
        self.asked: list[ResumeBotCommand] = []
        self.refuse: dict[str, str] = {}

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        assert isinstance(input_dto, ResumeBotCommand)
        self.asked.append(input_dto)
        reason = self.refuse.get(input_dto.bot_id)
        if reason is not None:
            return BotCommandResult.refused(
                BotRefusal.VENUE_NOT_READY, reason, input_dto.bot_id
            )
        return BotCommandResult.done(input_dto.bot_id)


class _World:
    def __init__(self) -> None:
        self.dispatcher = _Dispatcher()
        self.store = FakeBotStore()

    def resume(self, confirmed: str | None = None) -> ResumeRecoveringResult:
        handler = ResumeRecoveringForHostCommandHandler(self.store, self.dispatcher)
        return handler.execute(ResumeRecoveringForHostCommand(confirmed))

    def resumed(self) -> list[str]:
        return [command.bot_id for command in self.dispatcher.asked]


def test_every_recovering_bot_of_a_venue_gets_its_own_resume() -> None:
    world = _World()
    _bot(world.store, "aaaaaa", SPOT_TESTNET, BotLifecycleState.RECOVERING)
    _bot(world.store, "bbbbbb", SPOT_TESTNET, BotLifecycleState.RECOVERING)
    _bot(world.store, "cccccc", FUTURES_TESTNET, BotLifecycleState.RECOVERING)

    result = world.resume()

    assert sorted(world.resumed()) == ["aaaaaa", "bbbbbb", "cccccc"]
    assert {v.venue: (v.opened, v.bot_ids) for v in result.venues} == {
        "spot_testnet": (True, ("aaaaaa", "bbbbbb")),
        "futures_testnet": (True, ("cccccc",)),
    }


def test_a_bot_that_is_not_recovering_is_not_resumed() -> None:
    world = _World()
    _bot(world.store, "aaaaaa", SPOT_TESTNET, BotLifecycleState.RUNNING)
    _bot(world.store, "bbbbbb", SPOT_TESTNET, BotLifecycleState.HALTED)
    _bot(world.store, "cccccc", SPOT_TESTNET, BotLifecycleState.STOPPED)

    result = world.resume()

    assert world.resumed() == []
    assert result.venues == ()


def test_a_bot_whose_resume_is_refused_is_named_and_the_others_are_still_resumed() -> (
    None
):
    world = _World()
    world.dispatcher.refuse["aaaaaa"] = "unexpected open positions"
    _bot(world.store, "aaaaaa", SPOT_TESTNET, BotLifecycleState.RECOVERING)
    _bot(world.store, "bbbbbb", SPOT_TESTNET, BotLifecycleState.RECOVERING)

    (venue,) = world.resume().venues

    assert sorted(world.resumed()) == ["aaaaaa", "bbbbbb"]
    assert venue.opened is False
    assert "aaaaaa stays RECOVERING" in venue.note
    assert "unexpected open positions" in venue.note
    assert "bbbbbb" not in venue.note


def test_a_mainnet_venue_is_resumed_only_when_the_operator_typed_it() -> None:
    world = _World()
    _bot(world.store, "aaaaaa", SPOT_MAINNET, BotLifecycleState.RECOVERING)

    refused = world.resume()
    assert world.resumed() == []
    assert refused.venues[0].opened is False
    assert "--confirm-venue spot_mainnet" in refused.venues[0].note

    world.resume(confirmed="spot_testnet")
    assert world.resumed() == []  # another venue typed

    resumed = world.resume(confirmed="spot_mainnet")
    assert world.dispatcher.asked == [
        ResumeBotCommand("aaaaaa", real_money_confirmed=True)
    ]
    assert resumed.venues[0].opened is True
