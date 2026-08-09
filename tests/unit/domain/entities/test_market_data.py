import dataclasses
from datetime import datetime, timezone

import pytest

from src.domain.entities.market_data import MarketData


def test_market_data_successful_initialization():
    # Arrange
    open_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    close_time = datetime(2024, 1, 1, 12, 1, 0, tzinfo=timezone.utc)

    # Act
    market_data = MarketData(
        symbol="BTCUSDT",
        interval="1m",
        open_time=open_time,
        open_price=50000.0,
        high_price=50100.0,
        low_price=49900.0,
        close_price=50050.0,
        volume=100.0,
        close_time=close_time,
        quote_asset_volume=5005000.0,
        number_of_trades=1500,
        taker_buy_base_asset_volume=60.0,
        taker_buy_quote_asset_volume=3003000.0,
        is_closed=False,
    )

    # Assert
    assert market_data.symbol == "BTCUSDT"
    assert market_data.interval == "1m"
    assert market_data.open_time == open_time
    assert market_data.open_price == 50000.0
    assert market_data.high_price == 50100.0
    assert market_data.low_price == 49900.0
    assert market_data.close_price == 50050.0
    assert market_data.volume == 100.0
    assert market_data.close_time == close_time
    assert market_data.quote_asset_volume == 5005000.0
    assert market_data.number_of_trades == 1500
    assert market_data.taker_buy_base_asset_volume == 60.0
    assert market_data.taker_buy_quote_asset_volume == 3003000.0
    assert market_data.is_closed is False


def test_market_data_default_is_closed():
    # Arrange & Act
    market_data = MarketData(
        symbol="BTCUSDT",
        interval="1m",
        open_time=datetime.now(timezone.utc),
        open_price=50000.0,
        high_price=50100.0,
        low_price=49900.0,
        close_price=50050.0,
        volume=100.0,
        close_time=datetime.now(timezone.utc),
        quote_asset_volume=5005000.0,
        number_of_trades=1500,
        taker_buy_base_asset_volume=60.0,
        taker_buy_quote_asset_volume=3003000.0,
    )

    # Assert
    assert market_data.is_closed is True


def test_market_data_is_frozen():
    # Arrange
    market_data = MarketData(
        symbol="BTCUSDT",
        interval="1m",
        open_time=datetime.now(timezone.utc),
        open_price=50000.0,
        high_price=50100.0,
        low_price=49900.0,
        close_price=50050.0,
        volume=100.0,
        close_time=datetime.now(timezone.utc),
        quote_asset_volume=5005000.0,
        number_of_trades=1500,
        taker_buy_base_asset_volume=60.0,
        taker_buy_quote_asset_volume=3003000.0,
    )

    # Act & Assert
    with pytest.raises(dataclasses.FrozenInstanceError):
        market_data.close_price = 60000.0
