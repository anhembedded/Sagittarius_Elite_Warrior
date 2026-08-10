"""Mock MarketData generation, shared by every benchmark scenario so candle
shape (evenly-spaced 1m closes) never silently drifts between them."""

from datetime import UTC, datetime, timedelta

from Binace_Bot.src.domain.entities.market_data import MarketData

_BASE_TIME = datetime(2023, 1, 1, tzinfo=UTC)


def make_mock_candles(count: int, symbol: str = "BTCUSDT") -> list[MarketData]:
    """Oldest-first, 1-minute-spaced closes — matches what DashboardPresenter
    actually feeds IndicatorScriptRunner (see `_map_klines`'s ordering)."""
    candles = []
    for i in range(count):
        close_time = _BASE_TIME + timedelta(minutes=i)
        candles.append(
            MarketData(
                symbol=symbol,
                interval="1m",
                open_time=close_time - timedelta(minutes=1),
                open_price=100.0 + i,
                high_price=110.0 + i,
                low_price=90.0 + i,
                close_price=105.0 + i,
                volume=1000.0,
                close_time=close_time,
                quote_asset_volume=100000.0,
                number_of_trades=500,
                taker_buy_base_asset_volume=500.0,
                taker_buy_quote_asset_volume=50000.0,
                is_closed=True,
            )
        )
    return candles
