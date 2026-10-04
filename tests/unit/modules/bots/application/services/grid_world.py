"""A Spot venue the Grid executor can be run against, built from trading's ports.

`SimulatedBook` holds the account's open orders. `SimulatedSubmission` and
`SimulatedActivity` implement `IOrderSubmission` and `IAccountActivity` over it:
a LIMIT order rests until cancelled, a MARKET order is recorded and rests
nowhere, and every id is the one trading would generate for the request's tag.
A test scripts a refusal or a raise for the next submit or cancel. Fills are
not invented: a test feeds them to the executor, as the user data stream would.

`grid_world()` builds the real `GridExecutor` through the real factory, with an
inline queue (each task runs as it is posted) and a pacer that counts turns.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_executor import (
    GridExecutor,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_executor_factory import (
    GridExecutorDeps,
    GridExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_work_queue import (
    IBotWorkQueue,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_pacer import (
    IOrderPacer,
)
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.cancel_order_result import (
    CancelOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_page import (
    HistoryPage,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_request import (
    HistoryRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_activity import (
    IAccountActivity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
    IOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_entry_terms import (
    OrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_preview import (
    OrderPreview,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

SYMBOL = "BTCUSDT"
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


class SimulatedBook:
    """The account's open orders, and what was asked of the venue."""

    def __init__(self) -> None:
        self.open: dict[str, Order] = {}
        self.requests: list[OrderRequest] = []
        self.cancels: list[str] = []
        self.threads: list[str] = []
        self.refuse_next: list[ExecuteOrderSafetyGate | None] = []
        self.raise_next: list[Exception] = []
        self.cancel_refusals: list[ExecuteOrderSafetyGate] = []
        #: Cancels that report done but leave the order open (a cancel the
        #: exchange has not applied yet).
        self.sticky: set[str] = set()
        #: Called at each cancel, before it applies: what a test observes
        #: about the world at that moment.
        self.cancel_probe: Callable[[], None] | None = None


class SimulatedSubmission(IOrderSubmission):
    def __init__(self, book: SimulatedBook) -> None:
        self._book = book

    def preview(self, request: OrderRequest) -> OrderPreview:
        raise AssertionError("the executor never previews")

    def submit(
        self, request: OrderRequest, *, live: bool = False
    ) -> ExecuteOrderResult:
        assert live, "a bot's orders are live"
        self._book.requests.append(request)
        self._book.threads.append(threading.current_thread().name)
        if self._book.raise_next:
            raise self._book.raise_next.pop(0)
        if self._book.refuse_next:
            gate = self._book.refuse_next.pop(0)
            if gate is not None:
                return ExecuteOrderResult(gate, None, (), None)
        order = Order(
            client_order_id=generate_client_order_id(request.client_order_tag),
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            price=request.reference_price
            if request.order_type is OrderType.LIMIT
            else None,
            time_in_force=request.time_in_force,
            quote_quantity=request.quote_quantity,
        )
        if request.order_type is OrderType.LIMIT:
            self._book.open[order.client_order_id] = order
        return ExecuteOrderResult(None, None, (), order)

    def validate(self, request: OrderRequest) -> Order:
        raise AssertionError("the executor never validates")

    def cancel(self, symbol: str, client_order_id: str) -> CancelOrderResult:
        self._book.cancels.append(client_order_id)
        if self._book.cancel_probe is not None:
            self._book.cancel_probe()
        if self._book.cancel_refusals:
            return CancelOrderResult(self._book.cancel_refusals.pop(0), None)
        order = self._book.open.get(client_order_id)
        if client_order_id not in self._book.sticky:
            self._book.open.pop(client_order_id, None)
        return CancelOrderResult(None, order)


class SimulatedActivity(IAccountActivity):
    def __init__(self, book: SimulatedBook) -> None:
        self._book = book
        self.orders: list[OrderRecord] = []
        self.trades: list[TradeRecord] = []

    def summary(self) -> AccountSummary | None:
        return None

    def open_orders(self) -> tuple[Order, ...]:
        return tuple(self._book.open.values())

    def order_history(self, request: HistoryRequest) -> HistoryPage[OrderRecord]:
        return HistoryPage(tuple(self.orders), 0, len(self.orders), (SYMBOL,))

    def trade_history(self, request: HistoryRequest) -> HistoryPage[TradeRecord]:
        return HistoryPage(tuple(self.trades), 0, len(self.trades), (SYMBOL,))


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

    def fill(
        self, price: Decimal, quantity: str, fee: str = "0", asset: str = "USDT"
    ) -> None:
        order = self.book.open[self.open_ids_by_price()[price]]
        self.book.open.pop(order.client_order_id)
        self.executor.on_fill(
            BotOrderFill(
                order.client_order_id,
                order.side,
                price,
                Decimal(quantity),
                Decimal(fee),
                asset,
            )
        )


def terms_entry(maker: str = "0.001") -> OrderEntryTerms:
    return OrderEntryTerms(
        rules=SymbolOrderMetadata(
            symbol=SYMBOL,
            status="TRADING",
            step_size=STEP,
            tick_size=Decimal("0.01"),
            min_notional=Decimal(5),
            quantity_precision=None,
            price_precision=None,
            fetched_at=RUN_STARTED,
        ),
        commission=CommissionRate(SYMBOL, Decimal(maker), Decimal(maker)),
    )


def grid_world(
    state: BotLifecycleState = BotLifecycleState.STARTING,
    queue: IBotWorkQueue | None = None,
    config: dict[str, str] | None = None,
) -> GridWorld:
    book = SimulatedBook()
    activity = SimulatedActivity(book)
    session = FakeTradingSession()
    session.set_enabled(enabled=True)
    ports = fake_venue_ports(
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
        account_activity=activity,
    )
    store = FakeBotStore()
    clock = FakeBotClock()
    definition = BotDefinition("grid one", "grid", VENUE, SYMBOL, config or CONFIG)
    bot = Bot(BotId(BOT), definition, BotLifecycle(state, RUN_STARTED), RUN_STARTED)
    store.save(StoredBot(bot, {}))
    pacer = CountingPacer()
    factory = GridExecutorFactory(
        GridExecutorDeps(
            ports=FakeVenueTradingPorts(ports),
            store=store,
            clock=clock,
            caps=DEFAULT_OWNER_BUDGET_CAPS,
            queues=lambda _name: queue or InlineWorkQueue(),
            pacers=lambda _spacing: pacer,
        )
    )
    executor = factory.create(bot)
    return GridWorld(executor, book, activity, session, store, clock, pacer)


def minutes(count: int) -> timedelta:
    return timedelta(minutes=count)
