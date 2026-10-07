"""`EPIC-029` ADR D15 — keyed horizontal price lines and bands on a chart.

@details `ChartCard` draws candles, indicator curves, vertical regions and
markers, but no horizontal line a caller can name: a Grid's levels, its stop
loss and take profit, its average cost and its suggestion bands are all
horizontal. `chart_card.py` is baselined and cannot grow
(`baseline_god_files.json`), so this layer attaches to a card's price plot
from outside, through its public `plot_layout.main_plot`, and the card does
not know it exists.

Each key owns its items: `set_levels(key, ...)` replaces that key's lines
and leaves every other key's alone, the same "always the whole set"
contract as `ChartCard.set_script_markers`. The layer holds nothing but the
drawn items.

Lines and bands ignore the plot's auto-range (`ignoreBounds`), as the last
price line does: a far stop loss must not shrink the candles to a sliver.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

import pyqtgraph as pg
from PySide6 import QtCore, QtGui
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.price_line import (
    RIGHT_EDGE_TAG_ANCHORS,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    PRICE_LEVEL_LABEL_COLOR,
    PRICE_LEVEL_LABEL_DARK_COLOR,
)

#: Bands under the candles, lines above them.
_BAND_Z_VALUE = -20
_LINE_Z_VALUE = 20


class LineStyle(str, Enum):
    SOLID = "SOLID"
    DASH = "DASH"
    DOT = "DOT"


_QT_STYLES = {
    LineStyle.SOLID: QtCore.Qt.PenStyle.SolidLine,
    LineStyle.DASH: QtCore.Qt.PenStyle.DashLine,
    LineStyle.DOT: QtCore.Qt.PenStyle.DotLine,
}


@dataclass(frozen=True, slots=True)
class PriceLevel:
    """One horizontal line."""

    price: float
    color: str
    style: LineStyle = LineStyle.SOLID
    #: Shown at the right edge; empty draws no label.
    label: str = ""
    width: int = 1


@dataclass(frozen=True, slots=True)
class PriceBand:
    """One horizontal band between two prices."""

    lower: float
    upper: float
    color: str
    opacity: float = 0.12


class PriceLevelLayer:
    """@brief Keyed horizontal lines and bands on one price plot."""

    def __init__(self, plot: pg.PlotItem) -> None:
        self._plot = plot
        self._lines: dict[str, list[pg.InfiniteLine]] = {}
        self._bands: dict[str, list[pg.LinearRegionItem]] = {}

    def set_levels(self, key: str, levels: Sequence[PriceLevel]) -> None:
        """@brief Makes `levels` the whole set of lines under `key`."""
        self._remove(self._lines.pop(key, []))
        items = [self._line(level) for level in levels]
        for item in items:
            self._plot.addItem(item, ignoreBounds=True)
        self._lines[key] = items

    def set_bands(self, key: str, bands: Sequence[PriceBand]) -> None:
        """@brief Makes `bands` the whole set of bands under `key`."""
        self._remove(self._bands.pop(key, []))
        items = [self._band(band) for band in bands]
        for item in items:
            self._plot.addItem(item, ignoreBounds=True)
        self._bands[key] = items

    def clear(self, key: str) -> None:
        """@brief Removes every line and band under `key`."""
        self._remove(self._lines.pop(key, []))
        self._remove(self._bands.pop(key, []))

    def clear_all(self) -> None:
        for key in sorted(set(self._lines) | set(self._bands)):
            self.clear(key)

    def line_items(self, key: str) -> tuple[pg.InfiniteLine, ...]:
        """@brief The lines drawn under `key`, lowest price first."""
        return tuple(sorted(self._lines.get(key, []), key=lambda item: item.value()))

    def band_items(self, key: str) -> tuple[pg.LinearRegionItem, ...]:
        return tuple(self._bands.get(key, []))

    def _remove(self, items: Sequence[pg.GraphicsObject]) -> None:
        for item in items:
            self._plot.removeItem(item)

    @staticmethod
    def _line(level: PriceLevel) -> pg.InfiniteLine:
        pen = pg.mkPen(level.color, width=level.width, style=_QT_STYLES[level.style])
        line = pg.InfiniteLine(
            pos=level.price,
            angle=0,
            movable=False,
            pen=pen,
            label=level.label or None,
            labelOpts={
                "position": 1.0,
                "anchors": RIGHT_EDGE_TAG_ANCHORS,
                "color": label_text_color(level.color),
                "fill": pg.mkBrush(level.color),
                "movable": False,
            },
        )
        line.setZValue(_LINE_Z_VALUE)
        return line

    @staticmethod
    def _band(band: PriceBand) -> pg.LinearRegionItem:
        color = QtGui.QColor(pg.mkColor(band.color))
        color.setAlphaF(max(0.0, min(1.0, band.opacity)))
        item = pg.LinearRegionItem(
            values=(band.lower, band.upper),
            orientation="horizontal",
            movable=False,
            brush=pg.mkBrush(color),
            pen=pg.mkPen(None),
        )
        item.setZValue(_BAND_Z_VALUE)
        return item


def label_text_color(fill: str) -> str:
    """@brief Of the light and the dark label text, the one with the higher
    contrast against `fill` (WCAG 2 contrast ratio)."""
    light, dark = PRICE_LEVEL_LABEL_COLOR, PRICE_LEVEL_LABEL_DARK_COLOR
    if _contrast(fill, dark) > _contrast(fill, light):
        return dark
    return light


def _contrast(first: str, second: str) -> float:
    brighter, darker = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (brighter + 0.05) / (darker + 0.05)


#: WCAG 2's sRGB linearisation threshold and the luminance channel weights.
_SRGB_LINEAR_LIMIT = 0.03928
_RGB_WEIGHTS = (0.2126, 0.7152, 0.0722)


def _luminance(color: str) -> float:
    """WCAG 2 relative luminance of an sRGB colour."""
    qcolor = QtGui.QColor(color)
    channels = (qcolor.redF(), qcolor.greenF(), qcolor.blueF())
    linear = (
        c / 12.92 if c <= _SRGB_LINEAR_LIMIT else ((c + 0.055) / 1.055) ** 2.4
        for c in channels
    )
    return sum(
        weight * value for weight, value in zip(_RGB_WEIGHTS, linear, strict=True)
    )
