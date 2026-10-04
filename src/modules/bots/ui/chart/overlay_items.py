"""`EPIC-029G` — a `BotOverlay` as chart items: price lines, bands and fill
markers, styled by role (ADR D16).

@details Pure: no widget is touched here, so "the three surfaces draw the
same items" is a fact about one function. `BotOverlayDrawer` puts what this
returns on a chart. A new role is one entry in a style table below.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import (
    BotOverlay,
    FillSide,
    OverlayBand,
    OverlayBandRole,
    OverlayFill,
    OverlayLine,
    OverlayRole,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.marker_layer import (
    MarkerPoint,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.price_level_layer import (
    LineStyle,
    PriceBand,
    PriceLevel,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    AVERAGE_COST_COLOR,
    BEAR_COLOR,
    BULL_COLOR,
    EMPTY_LEVEL_COLOR,
    INDICATOR_BAND_COLOR,
    PARTIAL_LEVEL_COLOR,
    RANGE_EDGE_COLOR,
    STOP_LOSS_COLOR,
    SUGGESTION_BAND_COLOR,
    TAKE_PROFIT_COLOR,
)


@dataclass(frozen=True, slots=True)
class _LineStyle:
    color: str
    style: LineStyle
    width: int


_LINE_STYLES: dict[OverlayRole, _LineStyle] = {
    OverlayRole.BUY_LEVEL: _LineStyle(BULL_COLOR, LineStyle.DASH, 1),
    OverlayRole.SELL_LEVEL: _LineStyle(BEAR_COLOR, LineStyle.DASH, 1),
    OverlayRole.EMPTY_LEVEL: _LineStyle(EMPTY_LEVEL_COLOR, LineStyle.DOT, 1),
    OverlayRole.PARTIAL_LEVEL: _LineStyle(PARTIAL_LEVEL_COLOR, LineStyle.DASH, 2),
    OverlayRole.STOP_LOSS: _LineStyle(STOP_LOSS_COLOR, LineStyle.SOLID, 2),
    OverlayRole.TAKE_PROFIT: _LineStyle(TAKE_PROFIT_COLOR, LineStyle.SOLID, 2),
    OverlayRole.RANGE_EDGE: _LineStyle(RANGE_EDGE_COLOR, LineStyle.SOLID, 1),
    OverlayRole.AVERAGE_COST: _LineStyle(AVERAGE_COST_COLOR, LineStyle.DOT, 2),
}

_BAND_COLORS: dict[OverlayBandRole, str] = {
    OverlayBandRole.ATR_ZONE: SUGGESTION_BAND_COLOR,
    OverlayBandRole.BOLLINGER: INDICATOR_BAND_COLOR,
}


@dataclass(frozen=True, slots=True)
class OverlayItems:
    """What one overlay draws, in the chart's own vocabulary."""

    levels: tuple[PriceLevel, ...]
    bands: tuple[PriceBand, ...]
    markers: tuple[MarkerPoint, ...]


def overlay_items(overlay: BotOverlay) -> OverlayItems:
    """@brief The chart items for `overlay`, in its own order."""
    return OverlayItems(
        levels=tuple(_level(line) for line in overlay.lines),
        bands=tuple(_band(band) for band in overlay.bands),
        markers=tuple(_marker(fill) for fill in overlay.fills),
    )


def _level(line: OverlayLine) -> PriceLevel:
    style = _LINE_STYLES[line.role]
    return PriceLevel(
        float(line.price), style.color, style.style, line.label, style.width
    )


def _band(band: OverlayBand) -> PriceBand:
    return PriceBand(float(band.lower), float(band.upper), _BAND_COLORS[band.role])


def _marker(fill: OverlayFill) -> MarkerPoint:
    is_buy = fill.side is FillSide.BUY
    return (
        fill.time.timestamp(),
        float(fill.price),
        fill.label,
        BULL_COLOR if is_buy else BEAR_COLOR,
        "up" if is_buy else "down",
    )
