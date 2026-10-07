"""`MarketTickFeed` passes on only the ticks of the market its screen charts
(`EPIC-028C`).

@details Spot and Futures streams publish onto one bus, and `BTCUSDT@1m` is on
both at two prices. The real `MemoryEventBus` carries the events, so a Feed
that forwarded every tick, or read the market once at construction, fails
here.
"""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.market_tick_feed import (
    MarketTickFeed,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus

_VENUE = MarketDataVenue.MAINNET_PUBLIC


def _tick(market: MarketType, source: MarketDataVenue = _VENUE) -> MarketTickEvent:
    moment = datetime(2026, 9, 29, tzinfo=UTC)
    return MarketTickEvent(
        market_data=MarketData(
            symbol="BTCUSDT",
            interval="1m",
            open_time=moment,
            open_price=100.0,
            high_price=101.0,
            low_price=99.0,
            close_price=100.5,
            volume=1.0,
            close_time=moment,
            quote_asset_volume=100.5,
            number_of_trades=1,
            taker_buy_base_asset_volume=0.5,
            taker_buy_quote_asset_volume=50.0,
        ),
        market_type=market,
        market_data_venue=source,
    )


def test_only_the_screens_market_is_passed_on(qapp) -> None:
    bus = MemoryEventBus()
    feed = MarketTickFeed(bus, lambda: MarketType.FUTURES_USD_M, _VENUE)
    seen: list[MarketTickEvent] = []
    feed.marketTick.connect(seen.append)

    bus.emit(_tick(MarketType.SPOT))
    bus.emit(_tick(MarketType.FUTURES_USD_M))

    assert [event.market_type for event in seen] == [MarketType.FUTURES_USD_M]


def test_the_market_is_read_per_tick(qapp) -> None:
    """The Dev Board's chart changes market with its combo box while its Feed
    lives on; a Feed fixed at construction would keep the first market."""
    bus = MemoryEventBus()
    current = [MarketType.SPOT]
    feed = MarketTickFeed(bus, lambda: current[0], _VENUE)
    seen: list[MarketTickEvent] = []
    feed.marketTick.connect(seen.append)

    bus.emit(_tick(MarketType.SPOT))
    current[0] = MarketType.FUTURES_USD_M
    bus.emit(_tick(MarketType.SPOT))
    bus.emit(_tick(MarketType.FUTURES_USD_M))

    assert [event.market_type for event in seen] == [
        MarketType.SPOT,
        MarketType.FUTURES_USD_M,
    ]


def test_only_the_screens_venue_is_passed_on(qapp) -> None:
    """`BUG-172` — every venue streams its own market, so Spot Testnet's
    `BTCUSDT@1m` and Spot Mainnet's are two series on one bus: a screen of one
    hears nothing of the other."""
    bus = MemoryEventBus()
    feed = MarketTickFeed(bus, lambda: MarketType.SPOT, MarketDataVenue.SPOT_TESTNET)
    seen: list[MarketTickEvent] = []
    feed.marketTick.connect(seen.append)

    bus.emit(_tick(MarketType.SPOT, MarketDataVenue.MAINNET_PUBLIC))
    bus.emit(_tick(MarketType.SPOT, MarketDataVenue.SPOT_TESTNET))

    assert [event.market_data_venue for event in seen] == [MarketDataVenue.SPOT_TESTNET]
