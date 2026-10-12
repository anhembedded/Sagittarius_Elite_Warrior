"""Market data's section: how fresh each feed is, on the monotonic clock (`EPIC-038C`)."""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.application.health.feed_health_contributor import (
    FeedHealthContributor,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.health.last_tick_recorder import (
    LastTickRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _tick(symbol: str, market: MarketType) -> MarketTickEvent:
    moment = datetime(2026, 10, 7, tzinfo=UTC)
    return MarketTickEvent(
        market_data=MarketData(
            symbol=symbol,
            interval="1m",
            open_time=moment,
            open_price=1.0,
            high_price=1.0,
            low_price=1.0,
            close_price=1.0,
            volume=1.0,
            close_time=moment,
            quote_asset_volume=1.0,
            number_of_trades=1,
            taker_buy_base_asset_volume=0.0,
            taker_buy_quote_asset_volume=0.0,
        ),
        market_type=market,
        market_data_venue=MarketDataVenue.SPOT_TESTNET,
    )


def _world() -> tuple[FeedHealthContributor, MemoryEventBus, _Clock]:
    clock = _Clock()
    recorder = LastTickRecorder(clock)
    bus = MemoryEventBus()
    bus.on(MarketTickEvent, recorder.on_tick)  # the wiring `boot()` makes
    return FeedHealthContributor(recorder), bus, clock


def test_a_host_with_no_feed_open_says_null_not_zero() -> None:
    contributor, _, _ = _world()

    assert contributor.snapshot() == {"tick_age_s": None, "feeds": {}}


def test_each_feed_ages_from_its_own_last_candle() -> None:
    contributor, bus, clock = _world()
    bus.emit(_tick("BTCUSDT", MarketType.SPOT))
    clock.now += 30
    bus.emit(_tick("ETHUSDT", MarketType.SPOT))
    clock.now += 5

    section = contributor.snapshot()

    assert section["feeds"] == {"spot:BTCUSDT": 35, "spot:ETHUSDT": 5}
    assert section["tick_age_s"] == 5


def test_the_same_symbol_on_two_markets_is_two_feeds() -> None:
    contributor, bus, _ = _world()
    bus.emit(_tick("BTCUSDT", MarketType.SPOT))
    bus.emit(_tick("BTCUSDT", MarketType.FUTURES_USD_M))

    assert len(contributor.snapshot()["feeds"]) == 2  # type: ignore[arg-type]
