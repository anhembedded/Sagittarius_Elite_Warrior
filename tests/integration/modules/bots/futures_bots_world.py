"""`EPIC-039H` - the composed app over the fake exchange's **Futures** testnet, with its bots running.

@details The Futures twin of `grid_fake_exchange.booted`, on the same terms: `create_app()` builds
everything and the bots' executors are the production ones (`grid_executor_deps` binds the
exposure collaborators, the budgets and the risk watch of each venue profile); only the network
(the fake), the websocket the fake does not have, and each bot's queue and pacer are substituted.
The queue runs a bot's tasks on the poster's thread, one at a time and in order, so a journey is
deterministic without a wait; the pacer hands the user-data stream what the exchange reported
before each order, as the stream does within the spacing.

Fills reach the app through the Futures stream's own handler fed from the fake's queue (`EPIC-039C`),
exactly as the Spot journeys feed `SpotUserDataStream`. A test that wants the stream silent builds
the world with `stream_up=False` and calls `deliver` when it wants the reports to arrive.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_executor_factory import (
    GridExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_runtime_codec import (
    decode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.composition.executor_bindings import (
    grid_executor_deps,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_ticker import (
    IBotTicker,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_pacer import (
    IOrderPacer,
    OrderPacing,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_ticker import (
    FakeBotTicker,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_monotonic_clock import (
    FakeMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_user_data_stream import (
    FuturesUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScope,
    VenueTradingScopes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.kernel.app import App

from .futures_fake_exchange import FUTURES, SYMBOL
from .grid_fake_exchange import (
    DeliveringPacer,
    FakeExchange,
    FakeStreamSources,
    SerialQueue,
    _let_background_work_finish,
    app_config,
)

#: Four grids of 1,000 around the fake's mark of 64,000: 64,000 itself is the level nearest the
#: price and stays EMPTY, 62,000 and 63,000 buy, 65,000 and 66,000 sell. 600 USDT of margin at 3x
#: reaches 1,800 over four orders, so each carries 0.006 BTC (sized at the highest level, worth
#: 396 USDT, under trading's 500 a order). The stop loss sits above the liquidation price of the
#: worst case (O3).
GRID = {
    "lower": "62000",
    "upper": "66000",
    "grid_count": "4",
    "spacing": "ARITHMETIC",
    "capital_quote": "600",
    "direction": "LONG",
    "leverage": "3",
    "stop_loss": "price:50000",
    "take_profit": "price:80000",
}
#: The base each ladder order carries, and what the opening buys: the two SELL levels.
ORDER_QUANTITY = Decimal("0.006")
OPENING_QUANTITY = ORDER_QUANTITY * 2


@dataclass
class BootedFuturesBots:
    """One boot of the composed app over the shared fake Futures exchange."""

    engine: App
    exchange: FakeExchange
    store: IBotStore
    scope: VenueTradingScope
    stream: FuturesUserDataStream
    #: The Futures market data the bots' price watch streams through: the verified fake keeps
    #: the subscription bookkeeping and opens no socket.
    market: FakeMarketStream
    ticker: FakeBotTicker
    monotonic: FakeMonotonicClock

    def client(self) -> ITradingClient:
        """The venue's order client, live: what a user's own click on the exchange would use."""
        return self.scope.ports.client_factory.create(OrderSubmissionMode.LIVE)

    def deliver(self) -> None:
        """Hands the stream what the exchange reported since the last call."""
        for event in self.exchange.urls.futures_book.drain_user_data_events():
            asyncio.run(self.stream._handle_message(event))

    def move_price(
        self, price: Decimal | int, *, fill_at_most: Decimal | None = None
    ) -> None:
        self.exchange.urls.futures_book.move_price(
            SYMBOL, Decimal(price), fill_at_most=fill_at_most
        )
        self.deliver()

    def halt_for_a_down_stream(self, bot_id: str) -> None:
        """The halt a user-data stream that stayed down too long makes (`UserStreamWatch`): a
        reason a Futures venue does not wait out, so the halt takes the ladder off and closes the
        position, the journey these tests prove. A quiet price feed is no longer one (`BUG-270`)."""
        executor = self.engine.context.container.resolve(BotExecutors).get(bot_id)
        assert executor is not None
        executor.facts.halt_user_stream_down(timedelta(seconds=130))
        self.deliver()

    def bot(self, bot_id: str) -> Bot:
        return self.store.load(BotId(bot_id)).bot

    def runtime(self, bot_id: str) -> GridRuntime:
        return decode_runtime(self.store.load(BotId(bot_id)).runtime)

    def position(self) -> Decimal:
        """The exchange's signed position on the symbol; zero when flat."""
        return sum(
            (p.position_amt for p in self.client().get_positions(SYMBOL)), Decimal(0)
        )

    def resting(self) -> dict[str, tuple[str, Decimal, bool]]:
        """The exchange's open orders: id -> (side, price, reduce-only)."""
        return {
            str(o.client_order_id): (o.side.value, o.price, o.reduce_only)
            for o in self.client().get_open_orders(SYMBOL)
            if o.price is not None
        }


@contextmanager
def booted_futures_bots(
    exchange: FakeExchange,
    *,
    open_session: bool = True,
    stream_up: bool = True,
    pacers: Callable[[TradingVenue, OrderPacing], IOrderPacer] | None = None,
    limits: Mapping[str, object] | None = None,
) -> Iterator[BootedFuturesBots]:
    """The app with Futures Testnet on; its bots on the serial queue.

    @param open_session Seed the venue's session as open, what most journeys start from (the
    fake has no websocket for a real open to start).
    @param stream_up False is a user data stream that is down: the pacer delivers nothing, so
    the exchange's reports reach the app only when a test calls `deliver`.
    @param pacers The venue pacers the bots take their turns on, when a journey is about the
    pacing itself (`BUG-238`); the default hands the stream its reports and waits for nothing.
    @param limits Configuration keys that replace the journeys' defaults (`trading.bot_limits.*`).
    """
    engine = create_app(app_config(exchange.tmp_path, FUTURES, limits))
    container = engine.context.container
    holder: list[BootedFuturesBots] = []
    queue = SerialQueue()
    pacer = DeliveringPacer(lambda: holder[0].deliver() if stream_up else None)

    def executors(_container: IContainer) -> BotExecutors:
        deps = grid_executor_deps(
            container,
            queues=lambda _name: queue,
            pacers=pacers or (lambda _venue, _spacing: pacer),
        )
        return BotExecutors(GridExecutorFactory(deps))

    market = FakeMarketStream()
    ticker = FakeBotTicker()
    monotonic = FakeMonotonicClock()
    container.singleton(BotExecutors, executors)
    container.singleton(
        IMarketDataSources,
        FakeStreamSources(container.resolve(IMarketDataSources), market),
    )
    container.singleton(IBotTicker, ticker)
    container.singleton(IMonotonicClock, monotonic)
    engine.boot()
    scope = container.resolve(VenueTradingScopes).get(FUTURES)
    stream = scope.ports.user_data_stream
    assert isinstance(stream, FuturesUserDataStream)
    # What opening the websocket would have done: an `ACCOUNT_UPDATE` re-reads the position
    # through the connection's own client.
    stream.use_client_of_a_connection(
        scope.ports.client_factory.create(OrderSubmissionMode.VALIDATE_ONLY)
    )
    app = BootedFuturesBots(
        engine,
        exchange,
        container.resolve(IBotStore),
        scope,
        stream,
        market,
        ticker,
        monotonic,
    )
    holder.append(app)
    if open_session:
        scope.session_state.enable(set())
    try:
        yield app
    finally:
        _let_background_work_finish(container)
        engine.stop()
