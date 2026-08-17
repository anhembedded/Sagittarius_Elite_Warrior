r"""Measure a native cached-frame pan/zoom preview for BOT-098E.

Run from the Sagittarius-Engine workspace root:

    .\Sagittarius_Elite_Warrior\.venv\Scripts\python.exe -m \
        Sagittarius_Elite_Warrior.scripts.benchmarking.backtest_cached_frame_probe

This is a decision probe, not a production renderer or a shared-CI timing gate.
"""

from __future__ import annotations

import json
import math
import statistics
import time
from dataclasses import asdict, dataclass

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication

from Sagittarius_Elite_Warrior.scripts.benchmarking.backtest_chart_interaction import (
    _candles,
    _markers,
    _percentile_95,
    _volume,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
    ChartCard,
)

_INDICATOR_COUNT = 5
_VISIBLE_CANDLES = 150
_WARMUP_FRAMES = 30
_MEASURED_FRAMES = 240
_PAN_AMPLITUDE_RATIO = 0.12
_ZOOM_AMPLITUDE = 0.08
_CROSSHAIR_COLOR = QColor("#8a8f98")
_BACKGROUND_COLOR = QColor("#0b0e14")


@dataclass(frozen=True)
class CachedFrameProbeResult:
    preview_median_ms: float
    preview_p95_ms: float
    preview_updates_per_second: float
    final_commit_ms: float
    final_range_matches: bool
    frame_width: int
    frame_height: int


def _render_preview(
    source: QPixmap,
    target: QPixmap,
    *,
    pan_x: float,
    zoom: float,
    cursor: QPointF,
) -> None:
    target.fill(_BACKGROUND_COLOR)
    painter = QPainter(target)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
    center = QPointF(target.width() / 2.0, target.height() / 2.0)
    painter.translate(center.x() + pan_x, center.y())
    painter.scale(zoom, zoom)
    painter.translate(-center.x(), -center.y())
    painter.drawPixmap(0, 0, source)
    painter.resetTransform()
    painter.setPen(QPen(_CROSSHAIR_COLOR, 1.0, Qt.PenStyle.DashLine))
    painter.drawLine(QPointF(cursor.x(), 0.0), QPointF(cursor.x(), target.height()))
    painter.drawLine(QPointF(0.0, cursor.y()), QPointF(target.width(), cursor.y()))
    painter.end()


def _build_full_chart(app: QApplication) -> tuple[ChartCard, list[float]]:
    card = ChartCard("BTCUSDT")
    card.resize(1600, 900)
    card.show()
    candles = _candles()
    timestamps = [row[0] for row in candles]
    card.render_historical_data(candles)
    card.render_historical_volume(_volume(candles))
    for indicator_index in range(_INDICATOR_COUNT):
        key = f"ema_{indicator_index}"
        color = f"#{30 + indicator_index * 25:02x}B9F0"
        card.add_overlay_indicator(key, color)
        card.update_indicator_data(
            key,
            timestamps,
            [row[4] + indicator_index * 10.0 for row in candles],
        )
    card.set_script_markers("trades", _markers(candles))
    card.plot_layout.main_plot.setXRange(
        timestamps[2000],
        timestamps[2000 + _VISIBLE_CANDLES],
        padding=0,
    )
    app.processEvents()
    return card, timestamps


def _run_probe(app: QApplication) -> CachedFrameProbeResult:
    card, timestamps = _build_full_chart(app)
    viewport = card.plot_layout.widget.viewport()
    source = viewport.grab()
    target = QPixmap(source.size())
    frame_samples: list[float] = []
    total_frames = _WARMUP_FRAMES + _MEASURED_FRAMES

    for frame_index in range(total_frames):
        phase = frame_index / 12.0
        pan_x = math.sin(phase) * source.width() * _PAN_AMPLITUDE_RATIO
        zoom = 1.0 + math.cos(phase * 0.7) * _ZOOM_AMPLITUDE
        cursor = QPointF(
            source.width() * (0.5 + 0.25 * math.sin(phase * 0.5)),
            source.height() * 0.45,
        )
        started = time.perf_counter()
        _render_preview(
            source,
            target,
            pan_x=pan_x,
            zoom=zoom,
            cursor=cursor,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if frame_index >= _WARMUP_FRAMES:
            frame_samples.append(elapsed_ms)

    target_start = 2250
    expected_range = (
        timestamps[target_start],
        timestamps[target_start + _VISIBLE_CANDLES],
    )
    commit_started = time.perf_counter()
    card.plot_layout.main_plot.setXRange(*expected_range, padding=0)
    app.processEvents()
    final_commit_ms = (time.perf_counter() - commit_started) * 1000.0
    actual_range = card.plot_layout.main_plot.vb.viewRange()[0]
    final_range_matches = all(
        math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-6)
        for actual, expected in zip(actual_range, expected_range)
    )

    elapsed_seconds = sum(frame_samples) / 1000.0
    result = CachedFrameProbeResult(
        preview_median_ms=round(statistics.median(frame_samples), 3),
        preview_p95_ms=round(_percentile_95(frame_samples), 3),
        preview_updates_per_second=round(len(frame_samples) / elapsed_seconds, 2),
        final_commit_ms=round(final_commit_ms, 3),
        final_range_matches=final_range_matches,
        frame_width=source.width(),
        frame_height=source.height(),
    )
    card.cleanup()
    card.close()
    card.deleteLater()
    app.processEvents()
    return result


def main() -> None:
    app = QApplication.instance() or QApplication([])
    result = _run_probe(app)
    report = {
        "technique": "native QPixmap transform preview + exact final range commit",
        "business_state_source": "raw chart data on final commit",
        "result": asdict(result),
        "limitations": [
            "preview pixels are temporarily stale inside the gesture",
            "large pans expose uncached edges until a new frame is committed",
            "this probe measures frame composition, not end-to-end mouse delivery",
        ],
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
