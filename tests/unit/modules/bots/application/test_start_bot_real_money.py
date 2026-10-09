"""`EPIC-035V` (L6) — the Start use case, not the screen, refuses a mainnet start nobody confirmed.

The real-money question was asked by the Bots screen alone, so any other caller of
`StartBotCommand` started a mainnet bot unasked. The command carries the answer
(`real_money_confirmed`) and the handler refuses a mainnet bot without it, before
it reads the account.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_command_lock import (
    BotCommandLock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
    StartBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.readiness_world import (
    ReadinessWorld,
    readiness_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
)


class _CountingRunner(IBotRunner):
    """Records the starts it is asked for; everything else is not used here."""

    def __init__(self) -> None:
        self.started: list[str] = []

    def start(self, bot_id: str) -> BotCommandResult:
        self.started.append(bot_id)
        return BotCommandResult.done(bot_id)

    def pause(self, bot_id: str) -> None:
        raise NotImplementedError

    def resume(self, bot_id: str) -> None:
        raise NotImplementedError

    def stop(self, bot_id: str, base: object) -> None:  # type: ignore[override]
        raise NotImplementedError

    def confirm_resume(self, bot_id: str) -> None:
        raise NotImplementedError

    def has_resume_proposal(self, bot_id: str) -> bool:
        return False


def _start(
    world: ReadinessWorld, runner: IBotRunner, *, confirmed: bool
) -> BotCommandResult:
    handler = StartBotCommandHandler(
        world.store, runner, BotCommandLock(), world.reader, world.clock
    )
    return handler.execute(StartBotCommand(BOT, real_money_confirmed=confirmed))


def test_a_mainnet_start_nobody_confirmed_is_refused_before_anything_is_read() -> None:
    world = readiness_world(bot_venue=TradingVenue.SPOT_MAINNET)
    runner = _CountingRunner()

    result = _start(world, runner, confirmed=False)

    assert result.refusal is BotRefusal.REAL_MONEY_NOT_CONFIRMED
    assert "real money" in result.message
    assert runner.started == []
    assert world.session.ready_requests == 0


def test_a_confirmed_mainnet_start_goes_on_to_the_readiness() -> None:
    world = readiness_world(bot_venue=TradingVenue.SPOT_MAINNET)

    result = _start(world, _CountingRunner(), confirmed=True)

    assert result.refusal is not BotRefusal.REAL_MONEY_NOT_CONFIRMED


def test_a_testnet_start_needs_no_confirmation() -> None:
    world = readiness_world()
    runner = _CountingRunner()

    assert _start(world, runner, confirmed=False).accepted
    assert runner.started == [BOT]
