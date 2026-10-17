"""`EPIC-029J` J1a - the composed app with Spot Testnet **and** Futures Testnet on, bots running on both.

@details The union of `grid_fake_exchange.booted` and `futures_bots_world.booted_futures_bots`, on
the same terms: `create_app()` builds everything (one bots module, one store, one event router, two
venues' trading), and only the network (the one fake server, which serves `/api` and `/fapi`
side by side), the websocket the fake does not have, and each bot's queue and pacer are
substituted. Both venues trade `BTCUSDT`, so a bot's tag is the only thing that tells whose an
order, a fill or a profit is.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_ticker import (
    IBotTicker,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
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
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_user_data_stream import (
    SpotUserDataStream,
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

from .futures_bots_world import GRID as FUTURES_GRID
from .grid_fake_exchange import (
    BASELINE,
    DeliveringPacer,
    FakeExchange,
    FakeStreamSources,
    SerialQueue,
    _let_background_work_finish,
    app_config,
)
from .grid_fake_exchange import GRID as SPOT_GRID

SPOT = TradingVenue.SPOT_TESTNET
FUTURES = TradingVenue.FUTURES_TESTNET
SYMBOL = "BTCUSDT"
GRIDS = {SPOT: SPOT_GRID, FUTURES: FUTURES_GRID}


@dataclass
class BootedTwoVenues:
    """One boot of the composed app over the shared fake exchange, both venues on."""

    engine: App
    exchange: FakeExchange
    store: IBotStore
    scopes: dict[TradingVenue, VenueTradingScope]
    spot_stream: SpotUserDataStream
    futures_stream: FuturesUserDataStream
    market: FakeMarketStream
    ticker: FakeBotTicker
    monotonic: FakeMonotonicClock
    #: A bot's order turn delivers while a delivery is handing it a fill; `asyncio.run` cannot
    #: nest, so the inner call leaves the rest to the outer one, which drains both venues.
    _delivering: bool = False

    def client(self, venue: TradingVenue) -> ITradingClient:
        return self.scopes[venue].ports.client_factory.create(OrderSubmissionMode.LIVE)

    def deliver(self) -> None:
        """Hands each venue's stream what its exchange reported since the last call."""
        if self._delivering:
            return
        self._delivering = True
        try:
            self._drain_both()
        finally:
            self._delivering = False

    def _drain_both(self) -> None:
        for event in self.exchange.urls.spot_account.drain_user_data_events():
            if event["e"] == "executionReport":
                asyncio.run(self.spot_stream._handle_message(event))
        for event in self.exchange.urls.futures_book.drain_user_data_events():
            asyncio.run(self.futures_stream._handle_message(event))

    def move_price(
        self, venue: TradingVenue, price: Decimal | int, symbol: str = SYMBOL
    ) -> None:
        if venue is SPOT:
            self.exchange.urls.spot_account.set_last_price(symbol, Decimal(price))
        else:
            self.exchange.urls.futures_book.move_price(symbol, Decimal(price))
        self.deliver()

    def bot(self, bot_id: str) -> Bot:
        return self.store.load(BotId(bot_id)).bot

    def runtime(self, bot_id: str) -> GridRuntime:
        return decode_runtime(self.store.load(BotId(bot_id)).runtime)

    def resting(self, venue: TradingVenue, symbol: str = SYMBOL) -> set[str]:
        """The client order ids of the venue's open limit orders on the symbol: the ladder (a
        Futures protective stop has no price and is not a ladder order)."""
        return {
            str(order.client_order_id)
            for order in self.client(venue).get_open_orders(symbol)
            if order.price is not None
        }


@contextmanager
def booted_two_venues(
    exchange: FakeExchange,
    *,
    open_sessions: bool = True,
    retries: IBotRetryScheduler | None = None,
) -> Iterator[BootedTwoVenues]:
    """The app with Spot Testnet and Futures Testnet on; its bots on the serial queue.

    @param open_sessions Seed both venues' order sessions as open, what most journeys start
    from. False is a restart: the sessions stay closed until a deliberate action opens them."""
    config = app_config(exchange.tmp_path)
    config.load_dict({"exchange.trading_venues": [SPOT.value, FUTURES.value]})
    engine = create_app(config)
    container = engine.context.container
    holder: list[BootedTwoVenues] = []
    queue = SerialQueue()
    pacer = DeliveringPacer(lambda: holder[0].deliver())

    def executors(_container: IContainer) -> BotExecutors:
        deps = grid_executor_deps(
            container, queues=lambda _name: queue, pacers=lambda _venue, _spacing: pacer
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
    if retries is not None:
        container.singleton(IBotRetryScheduler, retries)
    container.singleton(IMonotonicClock, monotonic)
    engine.boot()
    scopes_of = container.resolve(VenueTradingScopes)
    scopes = {SPOT: scopes_of.get(SPOT), FUTURES: scopes_of.get(FUTURES)}
    spot_stream = scopes[SPOT].ports.user_data_stream
    futures_stream = scopes[FUTURES].ports.user_data_stream
    assert isinstance(spot_stream, SpotUserDataStream)
    assert isinstance(futures_stream, FuturesUserDataStream)
    futures_stream.use_client_of_a_connection(
        scopes[FUTURES].ports.client_factory.create(OrderSubmissionMode.VALIDATE_ONLY)
    )
    app = BootedTwoVenues(
        engine,
        exchange,
        container.resolve(IBotStore),
        scopes,
        spot_stream,
        futures_stream,
        market,
        ticker,
        monotonic,
    )
    holder.append(app)
    if open_sessions:
        scopes[SPOT].session_state.enable(set(), spot_baseline_holdings=dict(BASELINE))
        scopes[FUTURES].session_state.enable(set())
    try:
        yield app
    finally:
        _let_background_work_finish(container)
        engine.stop()
