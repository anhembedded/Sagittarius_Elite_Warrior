"""`BUG-204` — the use case behind Resume, for a bot the restart left RECOVERING.

@details Resume out of RECOVERING reopens the venue's order session, which on a
mainnet venue trades real money, so the use case asks for the answer to that
question as it does for a HALTED bot (`BUG-202`) and Start (`EPIC-035V`). A PAUSED
bot's resume opens nothing and asks nothing new.

`EPIC-042B`: a bot waiting in AWAITING_RECOVERY is resumed by the same re-plan as a HALTED one,
so the same real-money answer and the same readiness check apply to it. The design review found
the gate would otherwise have been skipped for a mainnet bot the moment the state was widened.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.resume_readiness import (
    ResumeReadinessReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
    ResumeBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.helpers import seed
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.readiness_world import (
    ReadinessWorld,
    readiness_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    CONFIG,
)

S = BotLifecycleState


class _RecordingRunner(IBotRunner):
    """`IBotRunner` as its contract states it: every command is queued (recorded)."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def start(self, bot_id: str) -> BotCommandResult:
        self.sent.append(("start", bot_id))
        return BotCommandResult.done(bot_id)

    def pause(self, bot_id: str) -> None:
        self.sent.append(("pause", bot_id))

    def resume(self, bot_id: str) -> BotCommandResult:
        self.sent.append(("resume", bot_id))
        return BotCommandResult.done(bot_id)

    def stop(self, bot_id: str, base: ExposureHandling) -> None:
        self.sent.append((f"stop:{base.value}", bot_id))

    def confirm_resume(self, bot_id: str) -> None:
        self.sent.append(("confirm_resume", bot_id))

    def has_resume_proposal(self, bot_id: str) -> bool:
        return False


@pytest.fixture
def world() -> ReadinessWorld:
    made = readiness_world()
    made.store.delete(BotId(BOT))
    return made


def _on_mainnet(store: FakeBotStore, state: S) -> None:
    bot = seed(store, "abc123", state, config=CONFIG, runtime={})
    mainnet = replace(
        bot, definition=replace(bot.definition, venue=TradingVenue.SPOT_MAINNET)
    )
    store.save(StoredBot(mainnet, {}))


def _handler(world: ReadinessWorld, runner: IBotRunner) -> ResumeBotCommandHandler:
    return ResumeBotCommandHandler(
        world.store,
        runner,
        ResumeReadinessReader(world.facts, world.ports, world.caps),
    )


def test_resuming_a_recovering_mainnet_bot_without_the_real_money_answer_is_refused(
    world: ReadinessWorld,
) -> None:
    runner = _RecordingRunner()
    _on_mainnet(world.store, S.RECOVERING)

    result = _handler(world, runner).execute(ResumeBotCommand("abc123"))

    assert result.refusal is BotRefusal.REAL_MONEY_NOT_CONFIRMED
    assert "recovering" in result.message
    assert runner.sent == []


def test_resuming_a_recovering_mainnet_bot_with_the_answer_is_queued(
    world: ReadinessWorld,
) -> None:
    runner = _RecordingRunner()
    _on_mainnet(world.store, S.RECOVERING)

    result = _handler(world, runner).execute(
        ResumeBotCommand("abc123", real_money_confirmed=True)
    )

    assert result.accepted
    assert runner.sent == [("resume", "abc123")]


def test_resuming_a_recovering_testnet_bot_needs_no_answer(
    world: ReadinessWorld,
) -> None:
    runner = _RecordingRunner()
    seed(world.store, "abc123", S.RECOVERING, config=CONFIG, runtime={})

    result = _handler(world, runner).execute(ResumeBotCommand("abc123"))

    assert result.accepted
    assert runner.sent == [("resume", "abc123")]


def test_resuming_a_paused_mainnet_bot_asks_for_no_new_answer(
    world: ReadinessWorld,
) -> None:
    """A PAUSED bot's orders still rest and its resume opens no session."""
    runner = _RecordingRunner()
    _on_mainnet(world.store, S.PAUSED)

    result = _handler(world, runner).execute(ResumeBotCommand("abc123"))

    assert result.accepted
    assert runner.sent == [("resume", "abc123")]


def test_resuming_a_waiting_mainnet_bot_without_the_real_money_answer_is_refused(
    world: ReadinessWorld,
) -> None:
    runner = _RecordingRunner()
    _on_mainnet(world.store, S.AWAITING_RECOVERY)

    result = _handler(world, runner).execute(ResumeBotCommand("abc123"))

    assert result.refusal is BotRefusal.REAL_MONEY_NOT_CONFIRMED
    assert "awaiting recovery" in result.message
    assert "awaiting_recovery" not in result.message
    assert runner.sent == []


def test_resuming_a_waiting_mainnet_bot_with_the_answer_still_meets_the_readiness_check(
    world: ReadinessWorld,
) -> None:
    """The readiness read is HALTED's (`BOT-174`); the waiting bot gets it too. This world does
    not enable the mainnet venue, so the read refuses and nothing is queued."""
    runner = _RecordingRunner()
    _on_mainnet(world.store, S.AWAITING_RECOVERY)

    result = _handler(world, runner).execute(
        ResumeBotCommand("abc123", real_money_confirmed=True)
    )

    assert result.refusal is BotRefusal.VENUE_NOT_READY
    assert runner.sent == []


def test_resuming_a_waiting_testnet_bot_needs_no_answer(
    world: ReadinessWorld,
) -> None:
    runner = _RecordingRunner()
    seed(world.store, "abc123", S.AWAITING_RECOVERY, config=CONFIG, runtime={})

    result = _handler(world, runner).execute(ResumeBotCommand("abc123"))

    assert result.accepted
    assert runner.sent == [("resume", "abc123")]
