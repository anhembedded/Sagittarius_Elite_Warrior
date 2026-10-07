"""`BUG-172` — a bot's candles are its own venue's market, built once per venue."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.venue_candles import (
    venue_candles,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    candle,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sources import (
    FakeMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer

_TESTNET = TradingVenue.SPOT_TESTNET
_MAINNET = TradingVenue.SPOT_MAINNET


def _container() -> tuple[StdLibContainer, FakeMarketDataSources]:
    sources = FakeMarketDataSources()
    for venue in (_TESTNET, _MAINNET):
        history = FakeHistoricalKlines()
        sources.serving(
            FakeMarketDataSources.ports(venue.market_data_venue, history=history)
        )
    container = StdLibContainer()
    container.singleton(IMarketDataSources, lambda _c: sources)
    return container, sources


def test_each_venues_feed_is_built_over_that_venues_ports() -> None:
    container, sources = _container()
    candles = venue_candles(container)

    for venue in (_TESTNET, _MAINNET):
        assert candles(venue).sync is sources.ports_for(venue.market_data_venue).sync


def test_the_feed_of_a_venue_loads_that_venues_stored_candles_only() -> None:
    container, sources = _container()
    testnet_history = sources.ports_for(_TESTNET.market_data_venue).history
    assert isinstance(testnet_history, FakeHistoricalKlines)
    testnet_history.seed([candle("BTCUSDT", 0)], MarketType.SPOT)
    candles = venue_candles(container)

    on_testnet = candles(_TESTNET).feed.load_history(
        "BTCUSDT", TimeFrame.ONE_MINUTE, 10
    )
    on_mainnet = candles(_MAINNET).feed.load_history(
        "BTCUSDT", TimeFrame.ONE_MINUTE, 10
    )

    assert len(on_testnet) == 1
    assert on_mainnet == ()


def test_a_venue_is_built_once_and_a_venue_never_asked_for_is_never_built() -> None:
    container, sources = _container()
    candles = venue_candles(container)

    assert candles(_TESTNET) is candles(_TESTNET)
    assert sources.asked == [_TESTNET.market_data_venue]
