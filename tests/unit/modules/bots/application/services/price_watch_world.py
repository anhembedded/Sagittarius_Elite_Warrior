"""`EPIC-035A` — the world the price watch tests run in.

Real `BotPriceWatch`, `BotExecutors`, `BotEventRouter` and Grid executor over the
simulated venue; the doubles are the verified `FakeMarketStream`, `FakeBotTicker`
and `FakeMonotonicClock`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.application.event_handlers.bot_event_router import (
    BotEventRouter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_price_watch import (
    BotPriceWatch,
    bot_price_owner,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_executor_factory import (
    GridExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_ticker import (
    FakeBotTicker,
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
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sources import (
    FakeMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    CONFIG,
    RUN_STARTED,
    SYMBOL,
    VENUE,
    GridWorld,
    grid_world,
)

S = BotLifecycleState
_TESTNET = VENUE.market_data_venue
SECOND = "c4d5e6"
_MAINNET = MarketDataVenue.MAINNET_PUBLIC
_AT = datetime(2026, 10, 8, 9, tzinfo=UTC)


@dataclass
class Watched:
    """A watch over one bot's world, and the two venues' fake streams."""

    world: GridWorld
    watch: BotPriceWatch
    executors: BotExecutors
    router: BotEventRouter
    ticker: FakeBotTicker
    testnet: FakeMarketStream
    mainnet: FakeMarketStream
    sources: FakeMarketDataSources

    def owner(self, bot_id: str = BOT) -> str:
        return bot_price_owner(BotId(bot_id))

    def tick(self, price: float) -> None:
        self.router.on_tick(tick(price))

    def save_state(self, state: S, bot_id: str = BOT, *, notify: bool = True) -> None:
        """The bot is saved in `state`; the watch hears of it unless `notify` is
        False (a bot saved before the app started)."""
        stored = self.world.store.load(BotId(bot_id))
        lifecycle = BotLifecycle(state, RUN_STARTED, None)
        bot = Bot(stored.bot.bot_id, stored.bot.definition, lifecycle, RUN_STARTED)
        self.world.store.save(StoredBot(bot, stored.runtime))
        if notify:
            self.watch.on_bot_changed(BotChangedEvent(bot_id=bot_id))


def tick(price: float) -> MarketTickEvent:
    return MarketTickEvent(
        MarketData(
            symbol=SYMBOL,
            interval="1m",
            open_time=_AT,
            open_price=price,
            high_price=price,
            low_price=price,
            close_price=price,
            volume=1.0,
            close_time=_AT,
            quote_asset_volume=1.0,
            number_of_trades=1,
            taker_buy_base_asset_volume=1.0,
            taker_buy_quote_asset_volume=1.0,
        ),
        market_type=MarketType.SPOT,
        market_data_venue=_TESTNET,
    )


def watched(
    world: GridWorld | None = None,
    testnet: FakeMarketStream | None = None,
    factory: GridExecutorFactory | None = None,
) -> Watched:
    world = world or running_world()
    testnet = testnet or FakeMarketStream()
    mainnet = FakeMarketStream()
    sources = FakeMarketDataSources()
    sources.serving(FakeMarketDataSources.ports(_TESTNET, stream=testnet))
    sources.serving(FakeMarketDataSources.ports(_MAINNET, stream=mainnet))
    executors = BotExecutors(factory or world.factory)
    ticker = FakeBotTicker()
    watch = BotPriceWatch(world.store, sources, executors, ticker)
    return Watched(
        world,
        watch,
        executors,
        BotEventRouter(world.store, executors),
        ticker,
        testnet,
        mainnet,
        sources,
    )


def running_world() -> GridWorld:
    """A RUNNING bot whose ladder rests on the simulated venue."""
    laid = grid_world()
    laid.executor.start()
    world = grid_world(state=S.RUNNING, runtime=laid.runtime())
    world.book.open = dict(laid.book.open)
    return world


def watched_running() -> Watched:
    return watched(running_world())


def add_second_bot(world: GridWorld) -> None:
    definition = BotDefinition("grid two", "grid", VENUE, SYMBOL, CONFIG)
    bot = Bot(
        BotId(SECOND), definition, BotLifecycle(S.RUNNING, RUN_STARTED, None), _AT
    )
    world.store.save(StoredBot(bot, world.store.load(BotId(BOT)).runtime))
