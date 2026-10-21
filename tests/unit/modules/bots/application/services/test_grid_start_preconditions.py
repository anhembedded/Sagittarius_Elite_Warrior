"""`EPIC-029E` — what must hold before a Grid starts, and the runner that checks it
(ADR §3.1, D6, D9).

Each precondition refuses by name and leaves the bot as it was; a refused budget
gives the lease back. What can be known before an order (the venue, the verdicts)
is the readiness reader's, asked by the Start use case first
(`test_start_bot_readiness.py`, `EPIC-034H`). When all hold, the runner moves the bot to STARTING, builds
its executor and queues the start, which lays the ladder.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.start.grid_start_preconditions import (
    GridStartPreconditions,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.symbol_brackets import (
    BracketsUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_grid_budgets import (
    IGridBudgets,
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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudget,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_ready_result import (
    SessionBlockReason,
    SessionReadyResult,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    CONFIG,
    SYMBOL,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.start_world import (
    StartWorld,
    start_world,
)

S = BotLifecycleState


def _bot(world: StartWorld) -> Bot:
    return world.store.load(BotId(BOT)).bot


def test_all_preconditions_held_register_the_budget_for_this_run() -> None:
    world = start_world()

    assert world.preconditions.check(_bot(world), world.clock.now()) is None

    registration = world.session.budgets[f"bot.{BOT}"]
    assert registration.tag == BOT
    assert registration.symbol == SYMBOL
    assert registration.run_started_at == world.clock.now()
    assert registration.budget.max_open_orders == 5
    assert registration.budget.max_exposure_quote == Decimal(1000)
    assert registration.budget.min_order_spacing == timedelta(milliseconds=250)
    assert not world.session.claim_symbol(SYMBOL, "manual")


def test_start_opens_a_closed_session_before_anything_else() -> None:
    """`EPIC-034C` — no switch was turned on first: the start reconciles the
    account and opens the session itself, once."""
    world = start_world()
    assert world.session.snapshot().enabled is False

    assert world.preconditions.check(_bot(world), world.clock.now()) is None

    assert world.session.snapshot().enabled is True
    assert world.session.ready_requests == 1


def test_a_start_passes_no_position_claim_so_every_position_refuses_it() -> None:
    """`BUG-250`: only a Resume or a Stop of a venue's own bot excuses a position; a Start of any
    bot does not, whatever other bots wait on the venue."""
    world = start_world()

    world.preconditions.check(_bot(world), world.clock.now())

    assert world.session.claims_given == [()]


def test_a_refused_reconciliation_refuses_the_start_with_the_switchs_words() -> None:
    """A position the app did not open refuses the start before a lease is
    claimed or a budget registered."""
    world = start_world()
    world.session.ready_answers(
        SessionReadyResult(
            ready=False,
            block_reason=SessionBlockReason.UNEXPECTED_POSITIONS,
            reconciled_positions=(),
            reconciled_open_orders=(),
        )
    )

    refusal = world.preconditions.check(_bot(world), world.clock.now())

    assert refusal is not None
    assert refusal.refusal is BotRefusal.VENUE_NOT_READY
    assert "unexpected open positions" in refusal.message
    assert world.session.budgets == {}
    assert world.session.claim_symbol(SYMBOL, "manual")


def test_a_symbol_held_by_another_owner_is_refused() -> None:
    world = start_world()
    world.session.claim_symbol(SYMBOL, "strategy")

    refusal = world.preconditions.check(_bot(world), world.clock.now())

    assert refusal is not None
    assert refusal.refusal is BotRefusal.SYMBOL_LEASED
    assert world.session.budgets == {}
    assert world.session.ready_requests == 0  # a refused start opens nothing


def test_a_refused_budget_gives_the_lease_back() -> None:
    world = start_world()
    world.session.register_owner_budget_answers(
        OwnerBudgetRegistrationResult(
            OwnerBudgetRefusal.ABOVE_GLOBAL_CAP, exceeded_cap="max_open_orders"
        )
    )

    refusal = world.preconditions.check(_bot(world), world.clock.now())

    assert refusal is not None
    assert refusal.refusal is BotRefusal.BUDGET_REFUSED
    assert "max_open_orders" in refusal.message
    assert world.session.claim_symbol(SYMBOL, "manual")


class _BudgetsThatCannotBeRead(IGridBudgets):
    """A position venue whose brackets, which the budget is capped by, cannot be read."""

    def budget_of(
        self, venue: TradingVenue, symbol: str, params: GridParams
    ) -> OwnerBudget:
        raise BracketsUnavailableError(f"{venue.value} has no brackets for {symbol}")


def test_a_budget_that_cannot_be_read_refuses_the_start_and_claims_nothing() -> None:
    """Review of #490: `budget_of` ran after the symbol was claimed, so a read that failed
    left the lease with a bot that never started."""
    world = start_world()
    preconditions = GridStartPreconditions(
        world.preconditions._ports, _BudgetsThatCannotBeRead()
    )

    refusal = preconditions.check(_bot(world), world.clock.now())

    assert refusal is not None
    assert refusal.refusal is BotRefusal.VENUE_NOT_READY
    assert "no brackets" in refusal.message
    assert world.session.claim_symbol(SYMBOL, "manual"), "the lease was left behind"
    assert world.session.budgets == {}


def test_the_runner_starts_a_draft_bot_through_to_running() -> None:
    world = start_world()

    result = world.runner.start(BOT)

    assert result.accepted
    assert _bot(world).state is S.RUNNING
    assert _bot(world).lifecycle.run_started_at == world.clock.now()
    assert len(world.book.open) == 4


def test_a_new_run_closes_the_previous_runs_worker_before_it_starts() -> None:
    world = start_world()
    world.runner.start(BOT)
    world.runner.stop(BOT, ExposureHandling.KEEP)
    assert _bot(world).state is S.STOPPED

    world.runner.start(BOT)

    """Closed before the new run is written: a task still queued on the old
    worker can no longer save a stale bot over the new run's file."""
    assert [queue.closed_with for queue in world.queues] == [S.STOPPED, None]
    assert _bot(world).state is S.RUNNING


def test_a_refused_start_leaves_the_bot_a_draft() -> None:
    world = start_world()
    world.session.ready_answers(
        SessionReadyResult(
            ready=False,
            block_reason=SessionBlockReason.CONNECTION_NOT_READY,
            reconciled_positions=(),
            reconciled_open_orders=(),
        )
    )

    result = world.runner.start(BOT)

    assert result.refusal is BotRefusal.VENUE_NOT_READY
    assert _bot(world).state is S.DRAFT
    assert world.book.requests == []


@pytest.mark.parametrize("state", [S.RUNNING, S.HALTED, S.ERROR])
def test_starting_an_active_bot_is_an_invalid_transition(
    state: BotLifecycleState,
) -> None:
    world = start_world()
    draft = _bot(world)
    world.store.save(
        StoredBot(
            Bot(draft.bot_id, draft.definition, BotLifecycle(state), draft.created_at),
            {},
        )
    )

    assert world.runner.start(BOT).refusal is BotRefusal.INVALID_TRANSITION


def test_a_definition_with_a_leverage_the_venue_does_not_allow_is_refused_before_anything_is_claimed() -> (
    None
):
    """`EPIC-039B` review: the check Start repeats refuses a Spot leverage above 1 itself,
    whatever readiness said a moment ago, and neither claims the symbol nor registers a
    budget at the multiplied capital."""
    world = start_world()
    refused_config = {**CONFIG, "direction": "LONG", "leverage": "3"}
    bot = Bot.draft(
        BotId(BOT),
        BotDefinition(
            "grid one", "grid", TradingVenue.SPOT_TESTNET, SYMBOL, refused_config
        ),
        world.clock.now(),
    )

    result = world.preconditions.check(bot, world.clock.now())

    assert result is not None
    assert result.refusal is BotRefusal.PARAMETERS_REFUSED
    assert "leverage" in result.message.lower()
    assert world.session.budgets == {}
    assert world.session.claim_symbol(SYMBOL, "someone else")


def test_start_opens_the_session_for_the_bot_it_starts() -> None:
    """`BOT-183`: a Start's opening is announced as the started bot's."""
    world = start_world()

    assert world.preconditions.check(_bot(world), world.clock.now()) is None

    assert world.session.opened_for == [BOT]
