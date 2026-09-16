from __future__ import annotations


def map_klines(klines: list) -> list:
    """
    @brief Converts a list of MarketData entities to the
    (t, o, h, l, c) tuple format expected by FastCandlestickItem.
    """
    return [
        (
            float(item.close_time.timestamp()),
            float(item.open_price),
            float(item.high_price),
            float(item.low_price),
            float(item.close_price),
        )
        for item in klines
    ]


def map_volume(klines: list) -> list:
    """
    @brief Converts a list of MarketData entities to the
    (t, volume, is_bullish) tuple format expected by VolumeItem.
    """
    return [
        (
            float(item.close_time.timestamp()),
            float(item.volume),
            item.close_price >= item.open_price,
        )
        for item in klines
    ]
