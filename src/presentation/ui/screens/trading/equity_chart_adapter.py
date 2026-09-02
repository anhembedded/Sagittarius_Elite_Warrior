"""`EPIC-021M` §2.4 — `EquitySample` -> `ChartCard`'s `OhlcCandle` tuple
shape, written fresh for live data rather than importing
`screens/backtest/logic/chart_canvas_view.py`'s `equity_curve_to_candles()`.

@details That function takes a different input shape
(`list[tuple[datetime, float]]`, a closed backtest's own equity curve) and
lives in `screens/backtest/`; importing it here would recreate exactly the
`qml/ -> screens/` dependency direction `EPIC-021L` inverted (`BUG-082`).
Two short functions of its own is cheaper than the reverse dependency.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.domain.trading.equity_sample import EquitySample
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.chart_card import (
    OhlcCandle,
)


def equity_sample_to_candle(sample: EquitySample) -> OhlcCandle:
    """@brief One point, as `ChartCard`'s open=high=low=close=equity trick
    (same reasoning `equity_curve_to_candles()` documents) — lets the
    "line" chart type render unmodified instead of teaching `ChartCard` a
    second, unrelated series kind."""
    value = float(sample.total)
    return (sample.captured_at.timestamp(), value, value, value, value)


def equity_samples_to_candles(samples: list[EquitySample]) -> list[OhlcCandle]:
    """@brief The full backlog, oldest-first (`EquityCurveRecorder.samples`'
    own order) — for the chart's initial seed on screen construction."""
    return [equity_sample_to_candle(sample) for sample in samples]
