"""`BUG-202` — `BotRunner.resume`: the order session opens for a HALTED bot only,
and a refused open queues nothing."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.adapters.venue_fresh_price_reader import (
    VenueFreshPriceReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_runner import (
    BotRunner,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_budgets import (
    SpotGridBudgets,
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
    RecordingPublisher,
    SimulatedActivity,
    SimulatedBook,
    SimulatedSubmission,
    derive_inventory_from,
    terms_entry,
)

S = BotLifecycleState

VENUE = TradingVenue.SPOT_TESTNET


@dataclass
class _World:
    store: FakeBotStore
    session: FakeTradingSession
    executors: BotExecutors
    runner: BotRunner


def _world(state: BotLifecycleState) -> _World:
    book = SimulatedBook()
    session = FakeTradingSession()
    derive_inventory_from(book, session)
    ports = FakeVenueTradingPorts(
        fake_venue_ports(
            VENUE,
            trading_session=session,
            order_submission=SimulatedSubmission(book),
            order_entry_terms=FakeOrderEntryTerms(
                terms_entry(),
                books={
                    SYMBOL: BestBidAsk(
                        SYMBOL, LAST_PRICE, Decimal(1), LAST_PRICE, Decimal(1)
                    )
                },
                notional_limit=CAP,
            ),
            account_activity=SimulatedActivity(book),
        )
    )
    store = FakeBotStore()
    clock = FakeBotClock()
    definition = BotDefinition("grid one", "grid", VENUE, SYMBOL, CONFIG)
    bot = Bot(BotId(BOT), definition, BotLifecycle(state, clock.now()), clock.now())
    store.save(StoredBot(bot, {}))
    executors = BotExecutors(
        GridExecutorFactory(
            GridExecutorDeps(
                ports,
                store,
                clock,
                DEFAULT_OWNER_BUDGET_CAPS,
                lambda _name: InlineWorkQueue(),
                lambda _spacing: CountingPacer(),
                FakeBotRetryScheduler(),
                FakeMonotonicClock(),
                VenueFreshPriceReader(ports),
                RecordingPublisher(),
                SpotGridBudgets(DEFAULT_OWNER_BUDGET_CAPS),
            )
        )
    )
    preconditions = GridStartPreconditions(
        ports, SpotGridBudgets(DEFAULT_OWNER_BUDGET_CAPS)
    )
    return _World(
        store, session, executors, BotRunner(store, clock, preconditions, executors)
    )


def test_a_halted_resume_whose_session_will_not_open_is_refused_and_queues_nothing() -> (
    None
):
    """`BUG-202`: a refused open must not fall through to the resume."""
    world = _world(S.HALTED)
    world.session.ready_answers(
        SessionReadyResult(
            ready=False,
            block_reason=SessionBlockReason.EMERGENCY_STOP_IN_PROGRESS,
            reconciled_positions=(),
            reconciled_open_orders=(),
        )
    )

    result = world.runner.resume(BOT)

    assert result.refusal is BotRefusal.VENUE_NOT_READY
    assert world.executors.get(BOT) is None
    assert world.session.budgets == {}


def test_a_halted_resume_opens_the_session_and_reaches_the_bots_executor() -> None:
    world = _world(S.HALTED)

    result = world.runner.resume(BOT)

    assert result.accepted, result.message
    assert world.session.snapshot().enabled is True
    assert world.executors.get(BOT) is not None


def test_a_paused_resume_opens_no_session() -> None:
    """A paused bot's orders still rest and its resume registers nothing."""
    world = _world(S.PAUSED)

    result = world.runner.resume(BOT)

    assert result.accepted, result.message
    assert world.session.ready_requests == 0
    assert world.executors.get(BOT) is not None
