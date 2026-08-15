"""Shared helpers for indicator-script tests (BOT-032)."""

from datetime import UTC, datetime, timedelta

import pytest

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData


def build_candle(close: float, index: int = 0) -> MarketData:
    """A minimal valid candle at a given close price. Only close_price matters
    to the scripts under test; the rest is filled with plausible values so the
    frozen MarketData entity can be constructed at all."""
    open_time = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(minutes=index)
    return MarketData(
        symbol="ETHUSDT",
        interval="1m",
        open_time=open_time,
        open_price=close,
        high_price=close + 1,
        low_price=close - 1,
        close_price=close,
        volume=10.0,
        close_time=open_time + timedelta(minutes=1),
        quote_asset_volume=1000.0,
        number_of_trades=5,
        taker_buy_base_asset_volume=5.0,
        taker_buy_quote_asset_volume=500.0,
    )


@pytest.fixture
def make_candle():
    return build_candle


@pytest.fixture
def run_script():
    """Feeds a whole close series through a script, returning the last bar's
    plotted lines."""

    def _run(script, closes):
        last = {}
        for index, close in enumerate(closes):
            last = script.compute(build_candle(close, index))
        return last

    return _run
