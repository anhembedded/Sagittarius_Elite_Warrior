"""`BotTickFeed` forwards the candles of one market and one venue (`BUG-172`).

@details Every venue streams its own market onto one bus, so Spot Testnet's
`BTCUSDT@1h` and Spot Mainnet's are two series. The Feed of the selected bot's
chart hears the venue it was told to and nothing else; told nothing, it hears
nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bot_tick_feed import BotTickFeed
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus

_TESTNET = MarketDataVenue.SPOT_TESTNET
_MAINNET = MarketDataVenue.MAINNET_PUBLIC


def _tick(
    source: MarketDataVenue, market: MarketType = MarketType.SPOT
) -> MarketTickEvent:
    moment = datetime(2026, 10, 7, tzinfo=UTC)
    return MarketTickEvent(
        market_data=MarketData(
            symbol="BTCUSDT",
            interval="1h",
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
        market_data_venue=source,
    )


def _heard(feed: BotTickFeed, bus: MemoryEventBus, *events: MarketTickEvent) -> int:
    heard: list[object] = []
    feed.candle.connect(heard.append)
    for event in events:
        bus.emit(event)
    return len(heard)


def test_only_the_venue_it_listens_to_is_forwarded(qapp) -> None:
    bus = MemoryEventBus()
    feed = BotTickFeed(bus, MarketType.SPOT)
    feed.listen_to(_TESTNET)

    assert _heard(feed, bus, _tick(_MAINNET), _tick(_TESTNET)) == 1


def test_told_nothing_it_hears_nothing(qapp) -> None:
    bus = MemoryEventBus()
    feed = BotTickFeed(bus, MarketType.SPOT)

    assert _heard(feed, bus, _tick(_TESTNET), _tick(_MAINNET)) == 0


def test_listening_can_move_to_another_venue_and_stop(qapp) -> None:
    bus = MemoryEventBus()
    feed = BotTickFeed(bus, MarketType.SPOT, _TESTNET)
    heard: list[object] = []
    feed.candle.connect(heard.append)

    bus.emit(_tick(_TESTNET))
    feed.listen_to(_MAINNET)
    bus.emit(_tick(_TESTNET))
    bus.emit(_tick(_MAINNET))
    feed.listen_to(None)
    bus.emit(_tick(_MAINNET))

    assert len(heard) == 2


def test_the_market_still_decides_beside_the_venue(qapp) -> None:
    bus = MemoryEventBus()
    feed = BotTickFeed(bus, MarketType.SPOT, _TESTNET)

    assert _heard(feed, bus, _tick(_TESTNET, MarketType.FUTURES_USD_M)) == 0
