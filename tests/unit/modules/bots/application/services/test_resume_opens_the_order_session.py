"""`BUG-202` — the one session step a Resume from HALTED shares with Start."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_budgets import (
    SpotGridBudgets,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.start.grid_start_preconditions import (
    GridStartPreconditions,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FakeBotClock,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
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
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    CONFIG,
    SYMBOL,
)

VENUE = TradingVenue.SPOT_TESTNET


def _world() -> tuple[GridStartPreconditions, FakeTradingSession, Bot]:
    session = FakeTradingSession()
    ports = FakeVenueTradingPorts(fake_venue_ports(VENUE, trading_session=session))
    bot = Bot(
        BotId(BOT),
        BotDefinition("grid one", "grid", VENUE, SYMBOL, CONFIG),
        BotLifecycle(BotLifecycleState.HALTED),
        FakeBotClock().now(),
    )
    preconditions = GridStartPreconditions(
        ports, SpotGridBudgets(DEFAULT_OWNER_BUDGET_CAPS)
    )
    return preconditions, session, bot


def test_a_resume_from_halted_opens_a_closed_session_and_claims_nothing() -> None:
    preconditions, session, bot = _world()
    assert session.snapshot().enabled is False

    assert preconditions.open_session_for_resume(bot, (bot,)) is None

    assert session.snapshot().enabled is True
    assert session.budgets == {}
    assert session.claim_symbol(SYMBOL, "manual")


def test_a_resume_whose_session_will_not_open_is_refused_in_the_sessions_words() -> (
    None
):
    preconditions, session, bot = _world()
    session.ready_answers(
        SessionReadyResult(
            ready=False,
            block_reason=SessionBlockReason.EMERGENCY_STOP_IN_PROGRESS,
            reconciled_positions=(),
            reconciled_open_orders=(),
        )
    )

    refusal = preconditions.open_session_for_resume(bot, (bot,))

    assert refusal is not None
    assert refusal.refusal is BotRefusal.VENUE_NOT_READY
    assert "Emergency stop is still running" in refusal.message
    assert session.snapshot().enabled is False
