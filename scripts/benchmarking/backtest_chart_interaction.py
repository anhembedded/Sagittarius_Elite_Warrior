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
from dataclasses import asdict, dataclass

import pyqtgraph as pg
from PySide6 import __version__ as pyside_version
from PySide6.QtWidgets import QApplication

from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
    ChartCard,
)

_CANDLE_COUNT = 6420
_MARKER_COUNT = 1112
_INDICATOR_COUNT = 5
_VISIBLE_CANDLES = 150
_MEASURED_FRAMES = 120
_WARMUP_FRAMES = 20
_START_TIMESTAMP = 1_700_000_000.0
_CANDLE_SECONDS = 60.0


@dataclass(frozen=True)
class ProfileResult:
    profile: str
    median_ms: float
    p95_ms: float
    updates_per_second: float
    range_callbacks: int
    coalesced_range_applies: int
    volume_applies: int
    indicator_applies: int
    stored_markers: int
    active_markers: int


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
) -> ProfileResult:
    card = ChartCard("BTCUSDT")
    card.resize(1600, 900)
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
    callback_count = 0

    def count_callback(_viewbox, _x_range) -> None:
        nonlocal callback_count
        callback_count += 1

    card.plot_layout.main_plot.vb.sigXRangeChanged.connect(count_callback)
    frame_costs: list[float] = []
    initial_range_applies = card.range_updates.applied_count
    initial_volume_applies = card.volume.applied_update_count
    initial_indicator_applies = card.indicators.applied_update_count
    total_frames = _WARMUP_FRAMES + _MEASURED_FRAMES
    max_start = _CANDLE_COUNT - _VISIBLE_CANDLES - 1
    for frame_index in range(total_frames):
        start_index = frame_index * 37 % max_start
        min_x = timestamps[start_index]
        max_x = timestamps[start_index + _VISIBLE_CANDLES]
        started = time.perf_counter()
        card.plot_layout.main_plot.setXRange(min_x, max_x, padding=0)
        app.processEvents()
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if frame_index >= _WARMUP_FRAMES:
            frame_costs.append(elapsed_ms)

    card.range_updates.flush_pending()
    app.processEvents()
    elapsed_seconds = sum(frame_costs) / 1000.0
    layer = card.indicators._marker_layer
    result = ProfileResult(
        profile=profile,
        median_ms=round(statistics.median(frame_costs), 3),
        p95_ms=round(_percentile_95(frame_costs), 3),
        updates_per_second=round(len(frame_costs) / elapsed_seconds, 2),
        range_callbacks=callback_count,
        coalesced_range_applies=card.range_updates.applied_count
        - initial_range_applies,
        volume_applies=card.volume.applied_update_count - initial_volume_applies,
        indicator_applies=card.indicators.applied_update_count
        - initial_indicator_applies,
        stored_markers=layer.stored_marker_count("trades"),
        active_markers=layer.active_marker_count("trades"),
    )
    card.cleanup()
    card.close()
    card.deleteLater()
    app.processEvents()
    return result


def main() -> None:
    app = QApplication.instance() or QApplication([])
    candles = _candles()
    profiles = (
        ("candles", False, False, False),
        ("candles+volume", True, False, False),
        ("candles+volume+5-indicators", True, True, False),
        ("candles+volume+5-indicators+1112-markers", True, True, True),
    )
    results = [
        _run_profile(
            app,
            profile,
            candles,
            with_volume=with_volume,
            with_indicators=with_indicators,
            with_markers=with_markers,
        )
        for profile, with_volume, with_indicators, with_markers in profiles
    ]
    report = {
        "environment": {
            "os": platform.platform(),
            "python": platform.python_version(),
            "pyside": pyside_version,
            "qt_platform": app.platformName(),
            "pyqtgraph": pg.__version__,
            "resolution": "1600x900",
        },
        "dataset": {
            "candles": _CANDLE_COUNT,
            "indicators": _INDICATOR_COUNT,
            "markers": _MARKER_COUNT,
            "visible_candles": _VISIBLE_CANDLES,
            "measured_updates": _MEASURED_FRAMES,
        },
        "profiles": [asdict(result) for result in results],
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
