"""Shared helpers for strategy tests (BOT-026)."""

from datetime import UTC, datetime, timedelta

import pytest

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


def build_candle(close: float, index: int = 0, symbol: str = "BTCUSDT") -> MarketData:
    """A minimal valid 1-minute candle at a given close price and bar index."""
    open_time = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(minutes=index)
    close_time = open_time + timedelta(minutes=1)
    return MarketData(
        symbol=symbol,
        interval=TimeFrame.ONE_MINUTE.value,
        open_time=open_time,
        open_price=close,
        high_price=close,
        low_price=close,
        close_price=close,
        volume=1000.0,
        close_time=close_time,
        quote_asset_volume=close * 1000.0,
        number_of_trades=10,
        taker_buy_base_asset_volume=500.0,
        taker_buy_quote_asset_volume=500.0 * close,
    )


def build_klines(closes: list[float], symbol: str = "BTCUSDT") -> list[MarketData]:
    return [build_candle(close, index, symbol) for index, close in enumerate(closes)]


@pytest.fixture
def make_candle():
    return build_candle


@pytest.fixture
def make_klines():
    return build_klines
