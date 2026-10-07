"""`BUG-172` — testnet candles are never served as mainnet ones.

@details Real SQLite, one directory per venue (`venue_directory`), the repository
the app builds. The same symbol, interval and market is written to two venues and
each venue reads back only its own, whichever way the question is put.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.database_manager import (
    DatabaseConfig,
    DatabaseManager,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.sqlalchemy_repository import (
    SQLAlchemyMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.venue_directory import (
    venue_directory,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    candle,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)

_SYMBOL = "BTCUSDT"
_MINUTE = TimeFrame.ONE_MINUTE


@pytest.fixture
def stores(
    tmp_path: Path,
) -> Iterator[dict[MarketDataVenue, SQLAlchemyMarketDataRepository]]:
    managers = {
        venue: DatabaseManager(
            DatabaseConfig(db_dir=venue_directory(str(tmp_path), venue))
        )
        for venue in MarketDataVenue
    }
    yield {
        venue: SQLAlchemyMarketDataRepository(manager)
        for venue, manager in managers.items()
    }
    for manager in managers.values():
        manager.dispose_all()


def test_a_candle_stored_for_one_venue_is_not_read_from_another(stores) -> None:
    testnet, mainnet = (
        stores[MarketDataVenue.SPOT_TESTNET],
        stores[MarketDataVenue.MAINNET_PUBLIC],
    )

    testnet.save_klines(MarketType.SPOT, [candle(_SYMBOL, 0, close_price=111.0)])

    assert mainnet.get_klines(MarketType.SPOT, _SYMBOL, _MINUTE) == []
    assert mainnet.has_any_klines(MarketType.SPOT, _SYMBOL) is False
    assert mainnet.get_latest_kline_time(MarketType.SPOT, _SYMBOL, _MINUTE) is None
    assert [
        k.close_price for k in testnet.get_klines(MarketType.SPOT, _SYMBOL, _MINUTE)
    ] == [111.0]


def test_the_same_series_on_two_venues_keeps_two_sets_of_prices(stores) -> None:
    mainnet = stores[MarketDataVenue.MAINNET_PUBLIC]
    spot_testnet = stores[MarketDataVenue.SPOT_TESTNET]

    mainnet.save_klines(MarketType.SPOT, [candle(_SYMBOL, 0, close_price=65000.0)])
    spot_testnet.save_klines(MarketType.SPOT, [candle(_SYMBOL, 0, close_price=64000.0)])

    assert [
        k.close_price for k in mainnet.get_klines(MarketType.SPOT, _SYMBOL, _MINUTE)
    ] == [65000.0]
    assert [
        k.close_price
        for k in spot_testnet.get_klines(MarketType.SPOT, _SYMBOL, _MINUTE)
    ] == [64000.0]


def test_clearing_one_venues_candles_leaves_the_others(stores) -> None:
    mainnet, testnet = (
        stores[MarketDataVenue.MAINNET_PUBLIC],
        stores[MarketDataVenue.SPOT_TESTNET],
    )
    mainnet.save_klines(MarketType.SPOT, [candle(_SYMBOL, 0)])
    testnet.save_klines(MarketType.SPOT, [candle(_SYMBOL, 0)])

    testnet.purge_all()

    assert testnet.has_any_klines(MarketType.SPOT, _SYMBOL) is False
    assert mainnet.has_any_klines(MarketType.SPOT, _SYMBOL) is True


def test_a_venues_shards_are_listed_by_that_venue_alone(stores) -> None:
    stores[MarketDataVenue.FUTURES_TESTNET].save_klines(
        MarketType.FUTURES_USD_M, [candle("ETHUSDT", 0)]
    )
    stores[MarketDataVenue.MAINNET_PUBLIC].save_klines(
        MarketType.FUTURES_USD_M, [candle(_SYMBOL, 0)]
    )

    assert stores[MarketDataVenue.FUTURES_TESTNET].list_available_shards(
        MarketType.FUTURES_USD_M
    ) == ["ETHUSDT"]
    assert stores[MarketDataVenue.MAINNET_PUBLIC].list_available_shards(
        MarketType.FUTURES_USD_M
    ) == [_SYMBOL]
