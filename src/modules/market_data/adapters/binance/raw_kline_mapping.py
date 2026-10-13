"""A raw Binance kline row as `MarketData` (moved out of `PythonBinanceClient`, `EPIC-039K`).

@details The client file sat at the 400-line ceiling; this is the one pure step it did that
needs no client, so it is a function of its own. Binance's row layout
(`GET /api/v3/klines`, `/fapi/v1/klines`): open time, open, high, low, close, volume, close
time, quote volume, trades, taker buy base volume, taker buy quote volume, ignore.
"""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData


def map_raw_klines(
    raw_klines: list[list], symbol: str, interval: str
) -> list[MarketData]:
    """@return one `MarketData` per raw row of `symbol` at `interval`, in the given order."""
    return [
        MarketData(
            symbol=symbol,
            interval=interval,
            open_time=datetime.fromtimestamp(k[0] / 1000.0, tz=UTC),
            open_price=float(k[1]),
            high_price=float(k[2]),
            low_price=float(k[3]),
            close_price=float(k[4]),
            volume=float(k[5]),
            close_time=datetime.fromtimestamp(k[6] / 1000.0, tz=UTC),
            quote_asset_volume=float(k[7]),
            number_of_trades=int(k[8]),
            taker_buy_base_asset_volume=float(k[9]),
            taker_buy_quote_asset_volume=float(k[10]),
        )
        for k in raw_klines
    ]
