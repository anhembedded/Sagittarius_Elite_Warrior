"""Where a chart's tags and axis labels are drawn, measured against the
widget the person sees (`BUG-176`).

A chart is a `GraphicsLayoutWidget`; what it draws outside its viewport is
cut, and a plot's view box clips its children to its own rect. So a tag or a
label is visible only when it lies inside both. Every number here is in scene
coordinates, where the viewport is `(0, 0, width, height)`.
"""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard

#: Rounding slack of the layout's float geometry, in pixels.
_SLACK = 0.5


def _outside(inner: QRectF, outer: QRectF, *, sideways_only: bool = False) -> bool:
    """Whether `inner` leaves `outer`; `sideways_only` leaves the height out,
    for a tag whose price is off the visible price range and so rightly is
    not drawn."""
    sideways = (
        inner.left() < outer.left() - _SLACK or inner.right() > outer.right() + _SLACK
    )
    if sideways_only:
        return sideways
    return (
        sideways
        or inner.top() < outer.top() - _SLACK
        or inner.bottom() > outer.bottom() + _SLACK
    )


def _label_rect(label: pg.TextItem) -> QRectF:
    return label.mapRectToScene(label.boundingRect())


def tag_problems(card: ChartCard) -> list[str]:
    """What of the chart's price tags is cut: the last-price tag and every
    price-level tag must lie inside the main plot's view box, which is inside
    the viewport."""
    widget = card.plot_layout.widget
    viewport = widget.mapToScene(widget.viewport().rect()).boundingRect()
    view_box = card.plot_layout.main_plot.vb
    box = view_box.mapRectToScene(view_box.boundingRect())
    # Every labelled line on the plot, wherever its owner added it: the last
    # price, a bot's grid levels, a strategy's stop.
    tags: dict[str, pg.TextItem] = {}
    for index, item in enumerate(card.plot_layout.main_plot.items):
        label = getattr(item, "label", None)
        if isinstance(item, pg.InfiniteLine) and isinstance(label, pg.TextItem):
            tags[f"line {index} ({label.toPlainText()!r})"] = label
    problems = []
    for name, label in tags.items():
        if not label.isVisible():
            continue
        rect = _label_rect(label)
        if _outside(rect, viewport, sideways_only=True):
            problems.append(
                f"{name} tag {_fmt(rect)} leaves the viewport {_fmt(viewport)}"
            )
        elif _outside(rect, box, sideways_only=True):
            problems.append(f"{name} tag {_fmt(rect)} leaves the plot {_fmt(box)}")
    return problems


def axis_problems(card: ChartCard) -> list[str]:
    """What of every plot's axes is cut: the axis lies inside the viewport
    and every tick text it draws lies inside the axis's own rect."""
    widget = card.plot_layout.widget
    viewport = widget.mapToScene(widget.viewport().rect()).boundingRect()
    problems = []
    for index, plot in enumerate(card.plot_layout.plots):
        for name in ("left", "bottom"):
            axis = plot.getAxis(name)
            if not axis.isVisible():
                continue
            own = axis.boundingRect()
            if _outside(axis.mapRectToScene(own), viewport):
                problems.append(f"plot {index} {name} axis leaves the viewport")
            image = QImage(8, 8, QImage.Format.Format_ARGB32)
            painter = QPainter(image)
            _spec, _ticks, texts = axis.generateDrawSpecs(painter)
            painter.end()
            for rect, _flags, text in texts:
                if _outside(rect, own):
                    problems.append(
                        f"plot {index} {name} axis text {text!r} {_fmt(rect)} "
                        f"leaves the axis {_fmt(own)}"
                    )
    return problems


def _fmt(rect: QRectF) -> str:
    return f"({rect.left():.0f}, {rect.top():.0f}, {rect.right():.0f}, {rect.bottom():.0f})"
