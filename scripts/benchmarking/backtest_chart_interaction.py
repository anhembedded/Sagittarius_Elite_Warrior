r"""Reproducible BOT-098 Backtest chart pan benchmark.

Run from the Sagittarius-Engine workspace root:

    .\Sagittarius_Elite_Warrior\.venv\Scripts\python.exe -m \
        Sagittarius_Elite_Warrior.scripts.benchmarking.backtest_chart_interaction

The output is diagnostic evidence, not a timing gate for shared CI runners.
"""

from __future__ import annotations

import json
import math
import platform
import statistics
import time
from argparse import ArgumentParser
from dataclasses import asdict, dataclass

import pyqtgraph as pg
from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QGraphicsView
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
    ChartCard,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.plot_layout import (
    ChartAntialiasMode,
)

_CANDLE_COUNT = 6420
_MARKER_COUNT = 1112
_INDICATOR_COUNT = 5
_VISIBLE_CANDLES = 150
_MEASURED_FRAMES = 120
_WARMUP_FRAMES = 20
_START_TIMESTAMP = 1_700_000_000.0
_CANDLE_SECONDS = 60.0
_VIEWPORT_UPDATE_MODES = {
    "minimal": QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate,
    "smart": QGraphicsView.ViewportUpdateMode.SmartViewportUpdate,
    "bounding": QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate,
    "full": QGraphicsView.ViewportUpdateMode.FullViewportUpdate,
}
_PAINTER_OPTIMIZATIONS = {
    "none": (),
    "bounds": (QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing,),
    "state": (QGraphicsView.OptimizationFlag.DontSavePainterState,),
    "both": (
        QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing,
        QGraphicsView.OptimizationFlag.DontSavePainterState,
    ),
}


@dataclass(frozen=True)
class ProfileResult:
    profile: str
    render_backend: str
    antialias_mode: str
    viewport_update_mode: str
    painter_optimization: str
    lod_enabled: bool
    visible_candles: int
    median_ms: float
    p95_ms: float
    median_set_range_ms: float
    p95_set_range_ms: float
    median_render_ms: float
    p95_render_ms: float
    updates_per_second: float
    range_callbacks: int
    coalesced_range_applies: int
    volume_applies: int
    indicator_applies: int
    stored_markers: int
    active_markers: int
    represented_markers: int
    rendered_candles: int
    rendered_volume_bars: int
    device_pixel_ratio: float
    logical_viewport_width: int
    physical_viewport_width: int


def _candles() -> list[tuple[float, float, float, float, float]]:
    rows = []
    for index in range(_CANDLE_COUNT):
        timestamp = _START_TIMESTAMP + index * _CANDLE_SECONDS
        base = 60_000.0 + index * 0.2 + math.sin(index / 19.0) * 80.0
        close = base + math.sin(index / 7.0) * 20.0
        rows.append(
            (timestamp, base, max(base, close) + 12.0, min(base, close) - 12.0, close)
        )
    return rows


def _volume(
    candles: list[tuple[float, float, float, float, float]],
) -> list[tuple[float, float, bool]]:
    return [
        (timestamp, 10.0 + index % 80, close >= open_price)
        for index, (timestamp, open_price, _high, _low, close) in enumerate(candles)
    ]


def _markers(
    candles: list[tuple[float, float, float, float, float]],
) -> list[tuple[float, float, str, str, str]]:
    rows = []
    for marker_index in range(_MARKER_COUNT):
        candle_index = marker_index * len(candles) // _MARKER_COUNT
        timestamp, _open, high, low, _close = candles[candle_index]
        is_entry = marker_index % 2 == 0
        rows.append(
            (
                timestamp,
                low if is_entry else high,
                "Entry" if is_entry else "Exit",
                "#0ECB81" if is_entry else "#F6465D",
                "up" if is_entry else "down",
            )
        )
    return rows


def _percentile_95(samples: list[float]) -> float:
    ordered = sorted(samples)
    return ordered[math.ceil(len(ordered) * 0.95) - 1]


def _run_profile(
    app: QApplication,
    profile: str,
    candles: list[tuple[float, float, float, float, float]],
    *,
    with_volume: bool,
    with_indicators: bool,
    with_markers: bool,
    with_crosshair: bool,
    use_opengl: bool,
    antialias_mode: ChartAntialiasMode,
    viewport_update_mode: str,
    painter_optimization: str,
    lod_enabled: bool,
    visible_candles: int,
    measured_frames: int,
    warmup_frames: int,
) -> ProfileResult:
    card = ChartCard(
        "BTCUSDT",
        use_opengl=use_opengl,
        antialias_mode=antialias_mode,
        lod_enabled=lod_enabled,
    )
    card.resize(1600, 900)
    card.plot_layout.widget.setViewportUpdateMode(
        _VIEWPORT_UPDATE_MODES[viewport_update_mode]
    )
    for optimization_flag in _PAINTER_OPTIMIZATIONS[painter_optimization]:
        card.plot_layout.widget.setOptimizationFlag(optimization_flag, True)
    card.show()
    card.render_historical_data(candles)
    timestamps = [row[0] for row in candles]

    if with_volume:
        card.render_historical_volume(_volume(candles))
    if with_indicators:
        for indicator_index in range(_INDICATOR_COUNT):
            key = f"ema_{indicator_index}"
            card.add_overlay_indicator(key, f"#{30 + indicator_index * 25:02x}B9F0")
            card.update_indicator_data(
                key,
                timestamps,
                [row[4] + indicator_index * 10.0 for row in candles],
            )
    if with_markers:
        card.set_script_markers("trades", _markers(candles))

    app.processEvents()
    chart_viewport = card.plot_layout.widget.viewport()
    device_pixel_ratio = chart_viewport.devicePixelRatioF()
    logical_viewport_width = chart_viewport.width()
    callback_count = 0

    def count_callback(_viewbox, _x_range) -> None:
        nonlocal callback_count
        callback_count += 1

    card.plot_layout.main_plot.vb.sigXRangeChanged.connect(count_callback)
    frame_costs: list[float] = []
    set_range_costs: list[float] = []
    render_costs: list[float] = []
    initial_range_applies = card.range_updates.applied_count
    initial_volume_applies = card.volume.applied_update_count
    initial_indicator_applies = card.indicators.applied_update_count
    total_frames = warmup_frames + measured_frames
    max_start = max(1, _CANDLE_COUNT - visible_candles - 1)
    for frame_index in range(total_frames):
        start_index = frame_index * 37 % max_start
        min_x = timestamps[start_index]
        max_x = timestamps[start_index + visible_candles]
        started = time.perf_counter()
        card.plot_layout.main_plot.setXRange(min_x, max_x, padding=0)
        if with_crosshair:
            scene_pos = card.plot_layout.main_plot.vb.mapViewToScene(
                QPointF(timestamps[start_index + visible_candles // 2], 60_000.0)
            )
            card.crosshair.handle_mouse_moved((scene_pos,))
        set_range_ms = (time.perf_counter() - started) * 1000.0
        render_started = time.perf_counter()
        app.processEvents()
        render_ms = (time.perf_counter() - render_started) * 1000.0
        elapsed_ms = set_range_ms + render_ms
        if frame_index >= warmup_frames:
            frame_costs.append(elapsed_ms)
            set_range_costs.append(set_range_ms)
            render_costs.append(render_ms)

    card.range_updates.flush_pending()
    app.processEvents()
    elapsed_seconds = sum(frame_costs) / 1000.0
    layer = card.indicators._marker_layer
    result = ProfileResult(
        profile=profile,
        render_backend=card.plot_layout.render_backend,
        antialias_mode=card.plot_layout.antialias_mode.value,
        viewport_update_mode=viewport_update_mode,
        painter_optimization=painter_optimization,
        lod_enabled=lod_enabled,
        visible_candles=visible_candles,
        median_ms=round(statistics.median(frame_costs), 3),
        p95_ms=round(_percentile_95(frame_costs), 3),
        median_set_range_ms=round(statistics.median(set_range_costs), 3),
        p95_set_range_ms=round(_percentile_95(set_range_costs), 3),
        median_render_ms=round(statistics.median(render_costs), 3),
        p95_render_ms=round(_percentile_95(render_costs), 3),
        updates_per_second=round(len(frame_costs) / elapsed_seconds, 2),
        range_callbacks=callback_count,
        coalesced_range_applies=card.range_updates.applied_count
        - initial_range_applies,
        volume_applies=card.volume.applied_update_count - initial_volume_applies,
        indicator_applies=card.indicators.applied_update_count
        - initial_indicator_applies,
        stored_markers=layer.stored_marker_count("trades"),
        active_markers=layer.active_marker_count("trades"),
        represented_markers=layer.represented_marker_count("trades"),
        rendered_candles=card.candlestick.last_render_candle_count,
        rendered_volume_bars=card.volume.last_applied_bar_count,
        device_pixel_ratio=round(device_pixel_ratio, 3),
        logical_viewport_width=logical_viewport_width,
        physical_viewport_width=round(logical_viewport_width * device_pixel_ratio),
    )
    card.cleanup()
    card.close()
    card.deleteLater()
    app.processEvents()
    return result


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend",
        choices=("cpu", "opengl"),
        default="cpu",
        help="Requested ChartCard viewport backend (default: cpu).",
    )
    parser.add_argument(
        "--viewport-update",
        choices=tuple(_VIEWPORT_UPDATE_MODES),
        default="minimal",
        help="QGraphicsView viewport update strategy.",
    )
    parser.add_argument(
        "--painter-optimization",
        choices=tuple(_PAINTER_OPTIMIZATIONS),
        default="none",
        help="QGraphicsView painter optimization experiment.",
    )
    parser.add_argument(
        "--antialias",
        choices=tuple(mode.value for mode in ChartAntialiasMode),
        default=ChartAntialiasMode.LAYERED.value,
        help="Global scene smoothing or layered line-only smoothing.",
    )
    parser.add_argument(
        "--lod",
        choices=("enabled", "disabled"),
        default="enabled",
        help="Enable or disable native OHLC/volume LOD for A/B measurement.",
    )
    parser.add_argument(
        "--visible-candles",
        type=int,
        default=_VISIBLE_CANDLES,
        help="Number of candles covered by each measured viewport.",
    )
    parser.add_argument(
        "--profile",
        choices=("all", "candles", "candles-volume", "full"),
        default="all",
        help="Run every profile or one focused layer profile.",
    )
    parser.add_argument(
        "--measured-frames",
        type=int,
        default=_MEASURED_FRAMES,
        help="Measured viewport updates per profile.",
    )
    parser.add_argument(
        "--warmup-frames",
        type=int,
        default=_WARMUP_FRAMES,
        help="Warm-up viewport updates per profile.",
    )
    args = parser.parse_args()
    visible_candles = max(1, min(args.visible_candles, _CANDLE_COUNT - 1))
    antialias_mode = ChartAntialiasMode(args.antialias)
    app = QApplication.instance() or QApplication([])
    candles = _candles()
    profiles = (
        ("candles", False, False, False, False),
        ("candles+volume", True, False, False, False),
        ("candles+volume+5-indicators", True, True, False, False),
        ("candles+volume+5-indicators+1112-markers", True, True, True, False),
        (
            "candles+volume+5-indicators+1112-markers+crosshair",
            True,
            True,
            True,
            True,
        ),
    )
    if args.profile == "candles":
        profiles = profiles[:1]
    elif args.profile == "candles-volume":
        profiles = profiles[1:2]
    elif args.profile == "full":
        profiles = profiles[-1:]
    results = [
        _run_profile(
            app,
            profile,
            candles,
            with_volume=with_volume,
            with_indicators=with_indicators,
            with_markers=with_markers,
            with_crosshair=with_crosshair,
            use_opengl=args.backend == "opengl",
            antialias_mode=antialias_mode,
            viewport_update_mode=args.viewport_update,
            painter_optimization=args.painter_optimization,
            lod_enabled=args.lod == "enabled",
            visible_candles=visible_candles,
            measured_frames=max(1, args.measured_frames),
            warmup_frames=max(0, args.warmup_frames),
        )
        for profile, with_volume, with_indicators, with_markers, with_crosshair in profiles
    ]
    report = {
        "environment": {
            "os": platform.platform(),
            "python": platform.python_version(),
            "pyside": pyside_version,
            "qt_platform": app.platformName(),
            "pyqtgraph": pg.__version__,
            "resolution": "1600x900",
            "primary_screen_device_pixel_ratio": round(
                app.primaryScreen().devicePixelRatio() if app.primaryScreen() else 1.0,
                3,
            ),
            "requested_backend": args.backend,
            "antialias_mode": antialias_mode.value,
            "viewport_update_mode": args.viewport_update,
            "painter_optimization": args.painter_optimization,
        },
        "dataset": {
            "candles": _CANDLE_COUNT,
            "indicators": _INDICATOR_COUNT,
            "markers": _MARKER_COUNT,
            "visible_candles": visible_candles,
            "measured_updates": max(1, args.measured_frames),
            "warmup_updates": max(0, args.warmup_frames),
        },
        "profiles": [asdict(result) for result in results],
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
