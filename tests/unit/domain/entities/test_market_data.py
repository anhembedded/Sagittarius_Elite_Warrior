from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData


def test_market_data_initialization():
    """Test successful initialization of MarketData and default values."""
    dt_open = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
    dt_close = datetime(2023, 1, 1, 12, 15, 0, tzinfo=UTC)

    data = MarketData(
        symbol="BTCUSDT",
        interval="15m",
        open_time=dt_open,
        open_price=100.0,
        high_price=110.0,
        low_price=90.0,
        close_price=105.0,
        volume=1000.0,
        close_time=dt_close,
        quote_asset_volume=105000.0,
        number_of_trades=50,
        taker_buy_base_asset_volume=500.0,
        taker_buy_quote_asset_volume=52500.0,
    )

    assert data.symbol == "BTCUSDT"
    assert data.interval == "15m"
    assert data.open_time == dt_open
    assert data.open_price == 100.0
    assert data.high_price == 110.0
    assert data.low_price == 90.0
    assert data.close_price == 105.0
    assert data.volume == 1000.0
    assert data.close_time == dt_close
    assert data.quote_asset_volume == 105000.0
    assert data.number_of_trades == 50
    assert data.taker_buy_base_asset_volume == 500.0
    assert data.taker_buy_quote_asset_volume == 52500.0
    assert data.is_closed is True  # Test default value


def test_market_data_immutability():
    """Test that MarketData is frozen (immutable)."""
    dt_open = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
    dt_close = datetime(2023, 1, 1, 12, 15, 0, tzinfo=UTC)

    data = MarketData(
        symbol="BTCUSDT",
        interval="15m",
        open_time=dt_open,
        open_price=100.0,
        high_price=110.0,
        low_price=90.0,
        close_price=105.0,
        volume=1000.0,
        close_time=dt_close,
        quote_asset_volume=105000.0,
        number_of_trades=50,
        taker_buy_base_asset_volume=500.0,
        taker_buy_quote_asset_volume=52500.0,
        is_closed=False,
    )

    with pytest.raises(FrozenInstanceError):
        data.open_price = 101.0

    with pytest.raises(FrozenInstanceError):
        data.is_closed = True
