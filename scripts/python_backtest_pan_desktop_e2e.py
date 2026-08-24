"""Desktop E2E pixel evidence for the Backtest chart host (BUG-009).

Why this exists
---------------
The chart host had no pixel-level coverage at any test level (a former
native C++/QML host existed alongside it and was deleted outright — this
is the sole host now). BUG-009 lived in exactly that blind spot: its unit
tests asserted view ranges and state flags and passed throughout, because
the *data* was always correct; the defect was entirely in what got painted.
This script asserts what the user actually sees during a real drag.

Run only on a machine with a real display session:
    python scripts/python_backtest_pan_desktop_e2e.py
"""

from __future__ import annotations

import os
import sys

if os.environ.get("QT_QPA_PLATFORM") in {"offscreen", "minimal"}:
    raise SystemExit(
        "Desktop E2E needs a real windowing session — unset QT_QPA_PLATFORM "
        f"(currently {os.environ.get('QT_QPA_PLATFORM')!r})"
    )

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
    ChartCard,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.cached_frame_interaction import (
    _BACKGROUND_COLOR,
)

#: Deliberately trending, not flat. Flat synthetic candles hide both defects
#: this script exists to catch: a Y-autoscale jump is invisible when every
#: candle sits at the same price, and a blank band is hard to distinguish
#: when neighbouring columns are identical.
_CANDLE_COUNT = 5000
_BASE_TIME = 1786768980.0
_VISIBLE_CANDLES = 155
_MAX_BLANK_WIDTH_RATIO = 0.02
_MAX_VERTICAL_JUMP_PIXELS = 2.0


def _build_card() -> ChartCard:
    card = ChartCard("BTCUSDT", cached_interaction=False)
    card.resize(1666, 620)
    card.show()
    if not QTest.qWaitForWindowExposed(card):
        raise RuntimeError("ChartCard was never exposed on the real compositor")

    candles = []
    volume = []
    for index in range(_CANDLE_COUNT):
        mid = 60000.0 + index * 2.0
        candles.append(
            (_BASE_TIME + index * 60, mid, mid + 30.0, mid - 30.0, mid + 10.0)
        )
        volume.append((_BASE_TIME + index * 60, 50.0 + (index % 40), index % 2 == 0))
    card.render_historical_data(candles)
    card.render_historical_volume(volume)

    timestamps = [_BASE_TIME + index * 60 for index in range(_CANDLE_COUNT)]
    for name, color, offset in (
        ("ema_20", "#ffa726", 0.3),
        ("ema_50", "#26c6da", 0.6),
        ("ema_200", "#ef5350", 1.2),
    ):
        card.add_overlay_indicator(name, color)
        card.update_indicator_data(
            name,
            timestamps,
            [60000.0 + index * 2.0 + offset for index in range(_CANDLE_COUNT)],
        )
    return card


def _blank_column_fraction(image, region) -> float:
    """Fraction of plot columns painted with nothing but overlay background."""
    rows = list(range(region.top() + 6, region.bottom() - 6, 8))
    blank = 0
    total = 0
    for x in range(region.left() + 2, region.right() - 2, 4):
        total += 1
        background = sum(
            1 for y in rows if QColor(image.pixelColor(x, y)) == _BACKGROUND_COLOR
        )
        if background >= len(rows) * 0.9:
            blank += 1
    return blank / total if total else 0.0


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    card = _build_card()
    plot = card.plot_layout.main_plot
    span = _VISIBLE_CANDLES * 60.0
    plot.setXRange(_BASE_TIME + 3000 * 60, _BASE_TIME + 3000 * 60 + span, padding=0)
    for _ in range(4):
        app.processEvents()

    canvas = card.plot_layout.widget
    viewport = canvas.viewport()
    view_rect = plot.vb.sceneBoundingRect()
    region = canvas.mapFromScene(view_rect).boundingRect()
    axis_strip_width = canvas.mapFromScene(view_rect.topLeft()).x()

    def axis_ink(image) -> int:
        """Counts painted (non-background) pixels in the price-axis strip.

        Pixel-equality is the wrong invariant here: during a correct live pan
        the Y axis re-autoscales, so its tick labels legitimately change. What
        must never happen is the labels *sliding out of the strip* with the
        drag, which empties it — that is the BUG-009 symptom of the whole
        frame moving instead of the data panning inside it.
        """
        ink = 0
        for x in range(axis_strip_width):
            for y in range(0, image.height(), 3):
                if QColor(image.pixelColor(x, y)) != _BACKGROUND_COLOR:
                    ink += 1
        return ink

    before_image = viewport.grab().toImage()
    before_axis = axis_ink(before_image)
    (_, _), _y_before = plot.vb.viewRange()

    start = canvas.mapFromScene(view_rect.center())
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)

    worst_blank = 0.0
    for offset in range(20, 601, 20):
        QTest.mouseMove(viewport, start + QPoint(offset, 0))
        app.processEvents()
        mid_image = viewport.grab().toImage()
        worst_blank = max(worst_blank, _blank_column_fraction(mid_image, region))
        ink = axis_ink(mid_image)
        if ink < before_axis * 0.5:
            raise RuntimeError(
                f"The price axis strip lost most of its content at offset "
                f"{offset}px ({ink} painted pixels vs {before_axis} before) — "
                "the chart frame is sliding instead of the data panning "
                "inside it (BUG-009's first symptom)."
            )

    (_, _), y_during = plot.vb.viewRange()
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=start + QPoint(600, 0))
    card.range_updates.flush_pending()
    app.processEvents()
    (_, _), y_after = plot.vb.viewRange()

    if worst_blank > _MAX_BLANK_WIDTH_RATIO:
        raise RuntimeError(
            f"{worst_blank:.0%} of the plot width was bare background mid-drag "
            "— the chart is showing captured pixels instead of real data "
            "(BUG-009's second symptom)."
        )

    height = max(1.0, y_during[1] - y_during[0])
    jump_pixels = abs(y_after[0] - y_during[0]) / height * region.height()
    if jump_pixels > _MAX_VERTICAL_JUMP_PIXELS:
        raise RuntimeError(
            f"The chart jumped {jump_pixels:.0f}px vertically on mouse release "
            "— Y autoscale was frozen during the drag and only corrected at "
            "commit (BUG-009's third symptom)."
        )

    card.cleanup()
    print(
        f"max blank band {worst_blank:.1%} of plot width | "
        f"vertical jump on release {jump_pixels:.1f}px | axis stationary"
    )
    print("PYTHON_BACKTEST_PAN_DESKTOP_E2E_OK")


if __name__ == "__main__":
    main()
