"""The Start world of `test_grid_start_preconditions.py`: a draft bot, a closed session and the runner over them."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.adapters.venue_fresh_price_reader import (
    VenueFreshPriceReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_budgets import (
    SpotGridBudgets,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_executor_factory import (
    GridExecutorDeps,
    GridExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.start.grid_start_preconditions import (
    GridStartPreconditions,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_runner import (
    BotRunner,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing import (
    free_loss_cap_hold,
)
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


class ClosableInlineQueue(InlineWorkQueue):
    """Records the bot's stored state at the moment it is closed."""

    def __init__(self, store: FakeBotStore) -> None:
        self._store = store
        self.closed_with: BotLifecycleState | None = None

    def close(self) -> None:
        self.closed_with = self._store.load(BotId(BOT)).bot.state


@dataclass
class StartWorld:
    store: FakeBotStore
    clock: FakeBotClock
    session: FakeTradingSession
    book: SimulatedBook
    preconditions: GridStartPreconditions
    runner: BotRunner
    queues: list[ClosableInlineQueue]


def start_world(
    cap: Decimal = CAP, venue: TradingVenue = TradingVenue.SPOT_TESTNET
) -> StartWorld:
    book = SimulatedBook()
    # Closed, as a fresh app boots: Start opens the session itself (`EPIC-034C`).
    session = FakeTradingSession()
    derive_inventory_from(book, session)
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
    preconditions = GridStartPreconditions(
        ports, SpotGridBudgets(DEFAULT_OWNER_BUDGET_CAPS)
    )
    queues: list[ClosableInlineQueue] = []

    def queue(_name: str) -> ClosableInlineQueue:
        queues.append(ClosableInlineQueue(store))
        return queues[-1]

    executors = BotExecutors(
        GridExecutorFactory(
            GridExecutorDeps(
                ports,
                store,
                clock,
                DEFAULT_OWNER_BUDGET_CAPS,
                queue,
                lambda _venue, _spacing: CountingPacer(),
                FakeBotRetryScheduler(),
                FakeMonotonicClock(),
                VenueFreshPriceReader(ports),
                RecordingPublisher(),
                SpotGridBudgets(DEFAULT_OWNER_BUDGET_CAPS),
            )
        )
    )
    runner = BotRunner(
        store, clock, preconditions, executors, free_loss_cap_hold.FreeLossCapHold()
    )
    return StartWorld(store, clock, session, book, preconditions, runner, queues)
