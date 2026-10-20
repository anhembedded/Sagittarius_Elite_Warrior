"""The labels a plot's bottom date axis draws for a visible range, read through the painter.

Shared by the tests that prove a chart's time axis reads in the display zone (`BUG-240`,
`BUG-243`): what is drawn, not which offset or zone the axis was handed."""

from __future__ import annotations

from datetime import UTC, datetime

from pyqtgraph import PlotWidget  # type: ignore[import-untyped]
from PySide6.QtGui import QImage, QPainter

_WIDTH_PX = 800


def utc_range(day: int, first_hour: int, hours: int) -> tuple[float, float]:
    """`hours` hours of January 2026 from `first_hour` o'clock UTC on `day`, as timestamps."""
    start = datetime(2026, 1, day, first_hour, tzinfo=UTC).timestamp()
    return start, start + hours * 3600


def drawn_labels(plot: PlotWidget, view: tuple[float, float]) -> list[str]:
    """The tick labels `plot`'s bottom axis draws while showing `view`."""
    plot.resize(_WIDTH_PX, 400)
    plot.setXRange(*view, padding=0)
    plot.grab()
    image = QImage(_WIDTH_PX, 100, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        _, _, text_specs = (
            plot.getPlotItem().getAxis("bottom").generateDrawSpecs(painter)
        )
    finally:
        painter.end()
    return [text for _, _, text in text_specs]
