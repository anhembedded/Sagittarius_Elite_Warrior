"""`StrategyOverlay` — an armed strategy's indicator lines and trend zones,
already computed, ready to draw.

@details `IStrategyChartOverlay.overlay_for()`'s return type. The chart
coordinators that consume this (`trading`'s and `backtest`'s) draw through
`support/charting`, exactly as before; what moved is where the throwaway
strategy is built and replayed — inside `strategy`, which owns
`BaseStrategy` — not how the lines get drawn.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OverlayLine:
    """One named indicator series, already coloured and sized."""

    name: str
    x: tuple[float, ...]
    y: tuple[float, ...]
    colour: str
    width: int


@dataclass(frozen=True, slots=True)
class TrendZone:
    """One shaded span on the chart: a start/end timestamp, a colour and
    an opacity."""

    start: float
    end: float
    colour: str
    opacity: float


@dataclass(frozen=True, slots=True)
class StrategyOverlay:
    """Everything one chart coordinator needs to draw one strategy's
    reading of one candle series, for one instant."""

    lines: tuple[OverlayLine, ...]
    zones: tuple[TrendZone, ...]
