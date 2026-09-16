def to_heikin_ashi(
    data: list[tuple[float, float, float, float, float]],
) -> list[tuple[float, float, float, float, float]]:
    """
    @brief Converts a sequence of (t, o, h, l, c) candles to Heikin Ashi candles.
    @details Pure function, no Qt/pyqtgraph dependency — independently testable.
    HA close = average of O/H/L/C. HA open = midpoint of the PREVIOUS candle's HA
    open/close (the very first candle seeds this with its own open/close, since
    there is no previous HA candle). HA high/low extend to include the HA body.
    """
    result: list[tuple[float, float, float, float, float]] = []
    if not data:
        return result

    prev_ha_open = data[0][1]
    prev_ha_close = data[0][4]

    for t, o, h, low, c in data:
        ha_close = (o + h + low + c) / 4.0
        ha_open = (prev_ha_open + prev_ha_close) / 2.0
        ha_high = max(h, ha_open, ha_close)
        ha_low = min(low, ha_open, ha_close)
        result.append((t, ha_open, ha_high, ha_low, ha_close))
        prev_ha_open, prev_ha_close = ha_open, ha_close

    return result
