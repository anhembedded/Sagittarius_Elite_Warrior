"""The Grid executor against the simulated Spot venue (`simulated_venue.py`).

`grid_world()` builds the real `GridExecutor` through the real factory, with an
inline queue (each task runs as it is posted) and a pacer that counts turns.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.adapters.venue_fresh_price_reader import (
    VenueFreshPriceReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_executor import (
    GridExecutor,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_executor_factory import (
    GridExecutorDeps,
    GridExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    decode_runtime,
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_work_queue import (
    IBotWorkQueue,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_pacer import (
    IOrderPacer,
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
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_entry_terms import (
    OrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
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
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.simulated_venue import (
    SYMBOL,
    SimulatedActivity,
    SimulatedBook,
    SimulatedSubmission,
)

BOT = "a3f9c1"
VENUE = TradingVenue.SPOT_TESTNET
STEP = Decimal("0.001")
LAST_PRICE = Decimal(121)
CAP = Decimal(300)
#: Five levels 100…140, the price at 121: BUYs at 100 and 110, 120 left
#: empty, SELLs at 130 and 140; 250 USDT a level, an opening of ~500 USDT.
CONFIG = {
    "lower": "100",
    "upper": "140",
    "grid_count": "4",
    "spacing": "ARITHMETIC",
    "capital_quote": "1000",
    "stop_loss": "price:90",
    "take_profit": "price:150",
}
RUN_STARTED = datetime(2026, 10, 4, 8, tzinfo=UTC)


class InlineWorkQueue(IBotWorkQueue):
    """Runs each task as it is posted, on the poster's thread."""

    def post(self, task: Callable[[], None]) -> None:
        task()

    def close(self) -> None:
        return None


class CountingPacer(IOrderPacer):
    def __init__(self) -> None:
        self.turns = 0

    def wait_turn(self) -> None:
        self.turns += 1


@dataclass
class GridWorld:
    """The executor and everything a test asserts against."""

    executor: GridExecutor
    book: SimulatedBook
    activity: SimulatedActivity
    session: FakeTradingSession
    store: FakeBotStore
    clock: FakeBotClock
    pacer: CountingPacer
    snapshot: FakeAccountSnapshot
    factory: GridExecutorFactory
    retries: FakeBotRetryScheduler
    #: The staleness clock (`EPIC-035A`): it moves only when a test moves it.
    monotonic: FakeMonotonicClock
    #: What the venue says of the symbol: a test changes its status here.
    terms: FakeOrderEntryTerms
    owner: str = f"bot.{BOT}"
    placed_ids: list[str] = field(default_factory=list)

    def state(self) -> BotLifecycleState:
        return self.store.load(BotId(BOT)).bot.state

    def open_ids_by_price(self) -> dict[Decimal, str]:
        return {
            order.price: order.client_order_id
            for order in self.book.open.values()
            if order.price is not None
        }

    def hold(self, quantity: str) -> None:
        """The account's BTC holding, as the venue reports it."""
        self.snapshot.answer_with(
            ExchangeConnectionStatus(
                venue=VENUE,
                reachable=True,
                failure=None,
                server_time_skew_ms=0,
                usdt_balance=Decimal(10000),
                position_mode=None,
                margin_type=None,
                open_position_count=None,
                holdings=(
                    SpotHolding("BTC", Decimal(quantity), Decimal(0), Decimal(0)),
                ),
            )
        )

    def set_status(self, status: str) -> None:
        """The exchange's status for the symbol from now on."""
        self.terms.answer_with(terms_entry(status=status))

    def derive(self, quantity: str, cost: str = "0") -> None:
        """What trading derives as the bot's inventory at the next registration."""
        self.session.register_owner_budget_answers(
            OwnerBudgetRegistrationResult(
                None, OwnerInventory(Decimal(quantity), Decimal(cost))
            )
        )

    def runtime(self) -> GridRuntime:
        return decode_runtime(self.store.load(BotId(BOT)).runtime)

    def fill(
        self, price: Decimal, quantity: str, fee: str = "0", asset: str = "USDT"
    ) -> None:
        order = self.book.open[self.open_ids_by_price()[price]]
        self.book.open.pop(order.client_order_id)
        self.executor.facts.on_fill(
            BotOrderFill(
                order.client_order_id,
                order.side,
                price,
                Decimal(quantity),
                Decimal(fee),
                asset,
            )
        )


def terms_entry(
    maker: str = "0.001",
    market_step: Decimal | None = None,
    status: str = "TRADING",
) -> OrderEntryTerms:
    return OrderEntryTerms(
        rules=SymbolOrderMetadata(
            symbol=SYMBOL,
            status=status,
            step_size=STEP,
            tick_size=Decimal("0.01"),
            min_notional=Decimal(5),
            quantity_precision=None,
            price_precision=None,
            fetched_at=RUN_STARTED,
            market_step_size=market_step,
        ),
        commission=CommissionRate(SYMBOL, Decimal(maker), Decimal(maker)),
    )


def grid_world(
    state: BotLifecycleState = BotLifecycleState.STARTING,
    queue: IBotWorkQueue | None = None,
    runtime: GridRuntime | None = None,
    recovering_from: BotLifecycleState | None = None,
    book_readable: bool = True,
    queues: Callable[[str], IBotWorkQueue] | None = None,
    market_step: Decimal | None = None,
    store_view: Callable[[FakeBotStore], IBotStore] | None = None,
) -> GridWorld:
    book = SimulatedBook()
    activity = SimulatedActivity(book)
    terms = FakeOrderEntryTerms(
        terms_entry(market_step=market_step),
        books={
            SYMBOL: BestBidAsk(SYMBOL, LAST_PRICE, Decimal(1), LAST_PRICE, Decimal(1))
        }
        if book_readable
        else {},
        notional_limit=CAP,
    )
    session = FakeTradingSession()
    session.set_enabled(enabled=True)
    snapshot = FakeAccountSnapshot()
    ports = fake_venue_ports(
        VENUE,
        trading_session=session,
        account_snapshot=snapshot,
        order_submission=SimulatedSubmission(book),
        order_entry_terms=terms,
        account_activity=activity,
    )
    venue_ports = FakeVenueTradingPorts(ports)
    store = FakeBotStore()
    clock = FakeBotClock()
    definition = BotDefinition("grid one", "grid", VENUE, SYMBOL, CONFIG)
    lifecycle = BotLifecycle(state, RUN_STARTED, recovering_from)
    bot = Bot(BotId(BOT), definition, lifecycle, RUN_STARTED)
    store.save(StoredBot(bot, encode_runtime(runtime) if runtime else {}))
    pacer = CountingPacer()
    retries = FakeBotRetryScheduler()
    monotonic = FakeMonotonicClock()
    factory = GridExecutorFactory(
        GridExecutorDeps(
            ports=venue_ports,
            store=store_view(store) if store_view else store,
            clock=clock,
            caps=DEFAULT_OWNER_BUDGET_CAPS,
            queues=queues or (lambda _name: queue or InlineWorkQueue()),
            pacers=lambda _spacing: pacer,
            retries=retries,
            monotonic=monotonic,
            prices=VenueFreshPriceReader(venue_ports),
        )
    )
    executor = factory.create(bot)
    return GridWorld(
        executor,
        book,
        activity,
        session,
        store,
        clock,
        pacer,
        snapshot,
        factory,
        retries,
        monotonic,
        terms,
    )


def recovering_world() -> GridWorld:
    """A bot saved while RUNNING and restored: RECOVERING, its ladder resting."""
    before = grid_world()
    before.executor.start()
    world = grid_world(
        state=BotLifecycleState.RECOVERING,
        runtime=before.runtime(),
        recovering_from=BotLifecycleState.RUNNING,
    )
    world.book.open = dict(before.book.open)
    world.derive("0")
    world.hold("0")
    return world


def quote_at(world: GridWorld, price: Decimal) -> None:
    """The venue's best bid and ask both at `price`."""
    world.terms.quote(BestBidAsk(SYMBOL, price, Decimal(1), price, Decimal(1)))


def minutes(count: int) -> timedelta:
    return timedelta(minutes=count)
