"""`EPIC-029E` — what must hold before a Grid starts, and the runner that checks it
(ADR §3.1, D6, D9).

Each precondition refuses by name and leaves the bot as it was; a refused budget
gives the lease back. What can be known before an order (the venue, the verdicts)
is the readiness reader's, asked by the Start use case first
(`test_start_bot_readiness.py`, `EPIC-034H`). When all hold, the runner moves the bot to STARTING, builds
its executor and queues the start, which lays the ladder.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.venue_fresh_price_reader import (
    VenueFreshPriceReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_runner import (
    BotRunner,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_executor_factory import (
    GridExecutorDeps,
    GridExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_start_preconditions import (
    GridStartPreconditions,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FakeBotClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_retry_scheduler import (
    FakeBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_monotonic_clock import (
    FakeMonotonicClock,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_ready_result import (
    SessionBlockReason,
    SessionReadyResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
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
    CAP,
    CONFIG,
    LAST_PRICE,
    SYMBOL,
    CountingPacer,
    InlineWorkQueue,
    SimulatedActivity,
    SimulatedBook,
    SimulatedSubmission,
    terms_entry,
)

S = BotLifecycleState


class _ClosableInlineQueue(InlineWorkQueue):
    """Records the bot's stored state at the moment it is closed."""

    def __init__(self, store: FakeBotStore) -> None:
        self._store = store
        self.closed_with: BotLifecycleState | None = None

    def close(self) -> None:
        self.closed_with = self._store.load(BotId(BOT)).bot.state


@dataclass
class _Start:
    store: FakeBotStore
    clock: FakeBotClock
    session: FakeTradingSession
    book: SimulatedBook
    preconditions: GridStartPreconditions
    runner: BotRunner
    queues: list[_ClosableInlineQueue]


def _start_world(
    cap: Decimal = CAP, venue: TradingVenue = TradingVenue.SPOT_TESTNET
) -> _Start:
    book = SimulatedBook()
    # Closed, as a fresh app boots: Start opens the session itself (`EPIC-034C`).
    session = FakeTradingSession()
    ports = FakeVenueTradingPorts(
        fake_venue_ports(
            TradingVenue.SPOT_TESTNET,
            trading_session=session,
            order_submission=SimulatedSubmission(book),
            order_entry_terms=FakeOrderEntryTerms(
                terms_entry(),
                books={
                    SYMBOL: BestBidAsk(
                        SYMBOL, LAST_PRICE, Decimal(1), LAST_PRICE, Decimal(1)
                    )
                },
                notional_limit=cap,
            ),
            account_activity=SimulatedActivity(book),
        )
    )
    store = FakeBotStore()
    clock = FakeBotClock()
    definition = BotDefinition("grid one", "grid", venue, SYMBOL, CONFIG)
    store.save(StoredBot(Bot.draft(BotId(BOT), definition, clock.now()), {}))
    preconditions = GridStartPreconditions(ports, DEFAULT_OWNER_BUDGET_CAPS)
    queues: list[_ClosableInlineQueue] = []

    def queue(_name: str) -> _ClosableInlineQueue:
        queues.append(_ClosableInlineQueue(store))
        return queues[-1]

    executors = BotExecutors(
        GridExecutorFactory(
            GridExecutorDeps(
                ports,
                store,
                clock,
                DEFAULT_OWNER_BUDGET_CAPS,
                queue,
                lambda _spacing: CountingPacer(),
                FakeBotRetryScheduler(),
                FakeMonotonicClock(),
                VenueFreshPriceReader(ports),
            )
        )
    )
    runner = BotRunner(store, clock, preconditions, executors)
    return _Start(store, clock, session, book, preconditions, runner, queues)


def _bot(world: _Start) -> Bot:
    return world.store.load(BotId(BOT)).bot


def test_all_preconditions_held_register_the_budget_for_this_run() -> None:
    world = _start_world()

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
    world = _start_world()
    assert world.session.snapshot().enabled is False

    assert world.preconditions.check(_bot(world), world.clock.now()) is None

    assert world.session.snapshot().enabled is True
    assert world.session.ready_requests == 1


def test_a_refused_reconciliation_refuses_the_start_with_the_switchs_words() -> None:
    """A position the app did not open refuses the start before a lease is
    claimed or a budget registered."""
    world = _start_world()
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
    world = _start_world()
    world.session.claim_symbol(SYMBOL, "strategy")

    refusal = world.preconditions.check(_bot(world), world.clock.now())

    assert refusal is not None
    assert refusal.refusal is BotRefusal.SYMBOL_LEASED
    assert world.session.budgets == {}
    assert world.session.ready_requests == 0  # a refused start opens nothing


def test_a_refused_budget_gives_the_lease_back() -> None:
    world = _start_world()
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


def test_the_runner_starts_a_draft_bot_through_to_running() -> None:
    world = _start_world()

    result = world.runner.start(BOT)

    assert result.accepted
    assert _bot(world).state is S.RUNNING
    assert _bot(world).lifecycle.run_started_at == world.clock.now()
    assert len(world.book.open) == 4


def test_a_new_run_closes_the_previous_runs_worker_before_it_starts() -> None:
    world = _start_world()
    world.runner.start(BOT)
    world.runner.stop(BOT, BaseHandling.KEEP)
    assert _bot(world).state is S.STOPPED

    world.runner.start(BOT)

    """Closed before the new run is written: a task still queued on the old
    worker can no longer save a stale bot over the new run's file."""
    assert [queue.closed_with for queue in world.queues] == [S.STOPPED, None]
    assert _bot(world).state is S.RUNNING


def test_a_refused_start_leaves_the_bot_a_draft() -> None:
    world = _start_world()
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
    world = _start_world()
    draft = _bot(world)
    world.store.save(
        StoredBot(
            Bot(draft.bot_id, draft.definition, BotLifecycle(state), draft.created_at),
            {},
        )
    )

    assert world.runner.start(BOT).refusal is BotRefusal.INVALID_TRANSITION
