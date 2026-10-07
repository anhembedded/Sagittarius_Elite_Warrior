"""One live candle, drawn on a `ChartCard`: a closed one is appended, the forming
one replaces the last."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard


def draw_live_candle(chart: ChartCard, candle: MarketData) -> None:
    """Draws `candle` in the chart's candles and its volume. Call on the Qt
    thread."""
    t = candle.close_time.timestamp()
    o, h, low, c = (
        float(candle.open_price),
        float(candle.high_price),
        float(candle.low_price),
        float(candle.close_price),
    )
    bullish = c >= o
    if candle.is_closed:
        chart.append_closed_candle(t, o, h, low, c)
        chart.append_closed_volume(t, float(candle.volume), bullish)
    else:
        chart.update_last_candle(t, o, h, low, c)
        chart.update_last_volume(t, float(candle.volume), bullish)
