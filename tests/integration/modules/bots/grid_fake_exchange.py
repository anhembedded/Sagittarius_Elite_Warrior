"""The composed app over the fake Binance server, for the bots journeys.

@details Shared by `test_grid_bot_against_fake_server.py` (`EPIC-029E`) and
`test_bots_tab_drives_the_executor.py` (`EPIC-029H`): `create_app()` builds
everything, and only the network, the fake's missing websocket and the bot's
queue and pacer are substituted (the first file's docstring says why for
each). The `exchange` fixture lives in this directory's `conftest.py`.
"""

from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_executor_factory import (
    GridExecutorDeps,
    GridExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    decode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_ticker import (
    IBotTicker,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_work_queue import (
    IBotWorkQueue,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_pacer import (
    IOrderPacer,
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
    MarketDataPorts,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_user_data_stream import (
    SpotUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScope,
    VenueTradingScopes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
from sagittarius_engine.kernel.app import App

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sanity"))
from binance_fake_server import FakeServerUrls

SPOT = TradingVenue.SPOT_TESTNET
SYMBOL = "BTCUSDT"
CONFIG_DIR = Path(__file__).resolve().parents[4] / "src" / "config"
#: The fake Spot account's balances before enabling: the user's own coins.
BASELINE = {"USDT": Decimal(100000), "BTC": Decimal(10)}
#: Six levels 800 apart around the fake's 50,000: 49,600 is the nearest and
#: stays EMPTY, 48,000 and 48,800 buy, 50,400 to 52,000 sell. 2,000 USDT over
#: five orders is 400 a level, under the app's per-order limit.
GRID = {
    "lower": "48000",
    "upper": "52000",
    "grid_count": "5",
    "spacing": "ARITHMETIC",
    "capital_quote": "2000",
    "stop_loss": "price:40000",
    "take_profit": "price:60000",
}
GET_LOOP_BINDINGS = (
    "binance.base_client.get_loop",
    "binance.async_client.get_loop",
    "binance.ws.reconnecting_websocket.get_loop",
    "binance.ws.streams.get_loop",
    "binance.ws.threaded_stream.get_loop",
    "binance.ws.depthcache.get_loop",
)


class FakeStreamSources(IMarketDataSources):
    """The app's market data, but every venue's live stream is one verified fake.

    Klines, sync and coverage stay the real ports over the fake Binance server;
    only the websocket is replaced, because the fake server has none and a real
    one would reach a real exchange (`EPIC-035A`: the bots' price watch opens a
    stream for every bot that is not at rest).
    """

    def __init__(self, inner: IMarketDataSources, stream: FakeMarketStream) -> None:
        self._inner = inner
        self._stream = stream
        self._ports: dict[MarketDataVenue, MarketDataPorts] = {}

    @property
    def default_venue(self) -> MarketDataVenue:
        return self._inner.default_venue

    def ports_for(self, venue: MarketDataVenue) -> MarketDataPorts:
        if venue not in self._ports:
            self._ports[venue] = replace(
                self._inner.ports_for(venue), stream=self._stream
            )
        return self._ports[venue]


class SerialQueue(IBotWorkQueue):
    """The bot's queue on the poster's thread: one task at a time, in order.
    A task that raises fails the test rather than being logged."""

    def __init__(self) -> None:
        self._tasks: deque[Callable[[], None]] = deque()
        self._running = False

    def post(self, task: Callable[[], None]) -> None:
        self._tasks.append(task)
        if self._running:
            return
        self._running = True
        try:
            while self._tasks:
                self._tasks.popleft()()
        finally:
            self._running = False

    def close(self) -> None:
        return None


class DeliveringPacer(IOrderPacer):
    """Each turn first hands the stream what the exchange reported so far."""

    def __init__(self, deliver: Callable[[], None]) -> None:
        self._deliver = deliver

    def wait_turn(self) -> None:
        self._deliver()


@dataclass
class BootedApp:
    """One boot of the composed app over the shared fake exchange."""

    engine: App
    urls: FakeServerUrls
    store: IBotStore
    scope: VenueTradingScope
    stream: SpotUserDataStream
    #: The Spot Testnet market data the bots' price watch streams through: the
    #: verified fake keeps the subscription bookkeeping and opens no socket, so
    #: no journey reaches a real exchange's market-data websocket.
    market: FakeMarketStream
    #: What the price watch ticks on and the clock it measures a quiet feed by.
    ticker: FakeBotTicker
    monotonic: FakeMonotonicClock

    def deliver(self) -> None:
        for event in self.urls.spot_account.drain_user_data_events():
            if event["e"] == "executionReport":
                asyncio.run(self.stream._handle_message(event))

    def bot(self, bot_id: str) -> Bot:
        return self.store.load(BotId(bot_id)).bot

    def runtime(self, bot_id: str) -> GridRuntime:
        return decode_runtime(self.store.load(BotId(bot_id)).runtime)

    def move_price(self, price: int) -> None:
        self.urls.spot_account.set_last_price(SYMBOL, Decimal(price))
        self.deliver()


def app_config(tmp_path: Path) -> ConfigManager:
    user_json = tmp_path / "user_config.json"
    user_json.write_text(json.dumps({}))
    config = ConfigManager()
    config.load_json(str(CONFIG_DIR / "app_config.json"))
    config.load_json(str(user_json), writable=True)
    config.load_dict(
        {
            "exchange.trading_venues": [SPOT.value],
            "bots.state_dir": str(tmp_path / "bots"),
            "trading.bot_limits.min_order_spacing_ms": 0,
        }
    )
    return config


@dataclass
class FakeExchange:
    urls: FakeServerUrls
    tmp_path: Path


@contextmanager
def booted(exchange: FakeExchange, *, open_session: bool = True) -> Iterator[BootedApp]:
    """The app with Spot Testnet on; its bots on the serial queue.

    @param open_session Seed the Spot session as open (what most journeys
    start from, the fake having no websocket for a real open to start). False
    leaves it closed, as a fresh app is: Start opens it itself (`EPIC-034C`).
    """
    engine = create_app(app_config(exchange.tmp_path))
    container = engine.context.container
    holder: list[BootedApp] = []
    queue = SerialQueue()
    pacer = DeliveringPacer(lambda: holder[0].deliver())

    def executors(_container: IContainer) -> BotExecutors:
        deps = GridExecutorDeps(
            ports=container.resolve(IVenueTradingPorts),
            store=container.resolve(IBotStore),
            clock=container.resolve(IBotClock),
            caps=container.resolve(OwnerBudgetCaps),
            queues=lambda _name: queue,
            pacers=lambda _spacing: pacer,
            retries=container.resolve(IBotRetryScheduler),
            monotonic=container.resolve(IMonotonicClock),
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
    scope = container.resolve(VenueTradingScopes).get(SPOT)
    stream = scope.ports.user_data_stream
    assert isinstance(stream, SpotUserDataStream)
    app = BootedApp(
        engine,
        exchange.urls,
        container.resolve(IBotStore),
        scope,
        stream,
        market,
        ticker,
        monotonic,
    )
    holder.append(app)
    if open_session:
        scope.session_state.enable(set(), spot_baseline_holdings=dict(BASELINE))
    try:
        yield app
    finally:
        _let_background_work_finish(container)
        engine.stop()


_DRAIN_SECONDS = 10.0


def _let_background_work_finish(container: IContainer) -> None:
    """Waits, on the pool's own count, for work a journey started and did not wait
    for. A fill asks for an account-summary read on the app's thread pool
    (`AccountSummaryRefreshService`); `engine.stop()` does not wait for it, so a
    read still running when the fixture removes the fake server's URL reaches a
    real host (the integration tier's network block fails the test on it)."""
    pool = container.resolve(IThreadManager)
    deadline = time.monotonic() + _DRAIN_SECONDS
    while time.monotonic() < deadline:
        stats = pool.stats()
        if stats is None or stats.in_flight == 0:
            return
        threading.Event().wait(0.005)


def resting(urls: FakeServerUrls) -> dict[str, tuple[str, Decimal]]:
    return {
        row["clientOrderId"]: (row["side"], Decimal(row["price"]))
        for row in urls.spot_account.open_orders(SYMBOL)
    }


def ladder(runtime: GridRuntime) -> dict[str, tuple[str, Decimal]]:
    return {o.client_order_id: (o.side.value, o.price) for o in runtime.open_orders}


def sides_by_price(runtime: GridRuntime) -> dict[Decimal, str]:
    return {price: side for side, price in ladder(runtime).values()}
