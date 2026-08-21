r"""Measure retained native camera updates with dense volume and indicators.

Run from the Sagittarius-Engine workspace root:

    .\Sagittarius_Elite_Warrior\.venv\Scripts\python.exe -m \
        Sagittarius_Elite_Warrior.scripts.benchmarking.native_chart_camera_probe

The output is local diagnostic evidence, not a shared-CI timing threshold.
"""

from __future__ import annotations

import json
import math
import statistics
import time

from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject, Qt, QUrl
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_indicator_snapshot import (
    NativeIndicatorSeries,
    pack_native_indicator_snapshot,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_runtime import (
    configure_native_chart_engine,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_snapshot import (
    pack_native_ohlcv_snapshot,
)
from shiboken6 import isValid

_CANDLE_COUNT = 6_420
_INDICATOR_COUNT = 5
_VISIBLE_CANDLES = 150
_MEASURED_UPDATES = 60
_WARMUP_UPDATES = 10
_WINDOW_WIDTH = 1_600
_WINDOW_HEIGHT = 900
_QML_DOCUMENT = b"""
import QtQuick
import Sagittarius.NativeChart 1.0

Item {
    width: 1600
    height: 900

    NativeChartItem {
        objectName: "nativeChartItem"
        anchors.fill: parent
    }
}
"""


def _wait_for_property(app: QApplication, item, name: str, expected: int) -> None:
    for _ in range(100):
        app.processEvents()
        if item.property(name) == expected:
            return
        QTest.qWait(10)
    raise RuntimeError(f"native chart did not publish {name}={expected}")


def _percentile_95(samples: list[float]) -> float:
    ordered = sorted(samples)
    return ordered[math.ceil(len(ordered) * 0.95) - 1]


def _create_chart_view() -> tuple[QQuickView, QQmlComponent, object, object]:
    view = QQuickView()
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    configure_native_chart_engine(view.engine(), required=True)
    component = QQmlComponent(view.engine())
    component.setData(_QML_DOCUMENT, QUrl())
    root_item = component.create()
    if component.errors() or root_item is None:
        raise RuntimeError("native chart QML component did not construct")
    view.setContent(QUrl(), component, root_item)
    view.resize(_WINDOW_WIDTH, _WINDOW_HEIGHT)
    chart_item = root_item.findChild(type(root_item), "nativeChartItem")
    if chart_item is None:
        raise RuntimeError("native chart QML item was not found")
    return view, component, root_item, chart_item


def _invoke_bool(chart_item: object, method: str, *arguments: object) -> bool:
    """Invoke a native QML method without relying on Python wrapper subclassing."""
    qt_arguments = tuple(Q_ARG(type(argument), argument) for argument in arguments)
    return QMetaObject.invokeMethod(
        chart_item,
        method,
        Qt.ConnectionType.DirectConnection,
        Q_RETURN_ARG(bool),
        *qt_arguments,
    )


def _snapshot() -> tuple[object, tuple[NativeIndicatorSeries, ...]]:
    timestamps: list[int] = []
    opens: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    volumes: list[float] = []
    indicator_values: list[list[float]] = [[] for _ in range(_INDICATOR_COUNT)]
    base_timestamp = 1_700_000_000_000
    candle_milliseconds = 60_000
    for index in range(_CANDLE_COUNT):
        base_price = 60_000.0 + index * 0.2 + math.sin(index / 19.0) * 80.0
        close_price = base_price + math.sin(index / 7.0) * 20.0
        timestamps.append(base_timestamp + index * candle_milliseconds)
        opens.append(base_price)
        highs.append(max(base_price, close_price) + 12.0)
        lows.append(min(base_price, close_price) - 12.0)
        closes.append(close_price)
        volumes.append(10.0 + index % 80)
        for indicator_index in range(_INDICATOR_COUNT):
            indicator_values[indicator_index].append(
                close_price + indicator_index * 10.0
            )

    snapshot = pack_native_ohlcv_snapshot(
        revision=1,
        timestamps=timestamps,
        opens=opens,
        highs=highs,
        lows=lows,
        closes=closes,
        volumes=volumes,
    )
    colors = (0xFF00BFFF, 0xFFF0B90B, 0xFFB44CFF, 0xFFFF8C00, 0xFF00C087)
    series = tuple(
        NativeIndicatorSeries(rgba=colors[index], values=tuple(indicator_values[index]))
        for index in range(_INDICATOR_COUNT)
    )
    return snapshot, series


def main() -> None:
    app = QApplication.instance() or QApplication([])
    view, _component, root_item, chart_item = _create_chart_view()
    try:
        view.show()
        app.processEvents()
        snapshot, series = _snapshot()
        if not _invoke_bool(chart_item, "submitSnapshot", snapshot):
            raise RuntimeError(chart_item.property("lastSnapshotError"))
        indicator_snapshot = pack_native_indicator_snapshot(
            revision=1,
            candle_count=_CANDLE_COUNT,
            series=series,
        )
        if not _invoke_bool(chart_item, "submitIndicatorSnapshot", indicator_snapshot):
            raise RuntimeError(chart_item.property("lastIndicatorSnapshotError"))
        view.grabWindow()
        _wait_for_property(app, chart_item, "renderedRevision", 1)
        if not _invoke_bool(
            chart_item,
            "setViewport",
            0.0,
            float(_VISIBLE_CANDLES),
        ):
            raise RuntimeError(chart_item.property("lastViewportError"))
        view.grabWindow()
        _wait_for_property(
            app,
            chart_item,
            "renderedCameraRevision",
            chart_item.property("cameraRevision"),
        )

        initial_volume_builds = chart_item.property("volumeGeometryBuildCount")
        initial_indicator_builds = chart_item.property("indicatorGeometryBuildCount")
        samples: list[float] = []
        final_camera_revision = chart_item.property("cameraRevision")
        for update_index in range(_WARMUP_UPDATES + _MEASURED_UPDATES):
            start_index = update_index * 37 % (_CANDLE_COUNT - _VISIBLE_CANDLES - 1)
            started = time.perf_counter()
            if not _invoke_bool(
                chart_item,
                "setViewport",
                float(start_index),
                float(start_index + _VISIBLE_CANDLES),
            ):
                raise RuntimeError(chart_item.property("lastViewportError"))
            view.grabWindow()
            app.processEvents()
            if update_index >= _WARMUP_UPDATES:
                samples.append((time.perf_counter() - started) * 1000.0)
            final_camera_revision = chart_item.property("cameraRevision")

        _wait_for_property(
            app,
            chart_item,
            "renderedCameraRevision",
            final_camera_revision,
        )
        elapsed_seconds = sum(samples) / 1000.0
        report = {
            "qt_platform": app.platformName(),
            "logical_resolution": f"{_WINDOW_WIDTH}x{_WINDOW_HEIGHT}",
            "device_pixel_ratio": chart_item.property("renderDevicePixelRatio"),
            "indicator_pixel_columns": chart_item.property("indicatorPixelColumnCount"),
            "candles": _CANDLE_COUNT,
            "indicators": _INDICATOR_COUNT,
            "visible_candles": _VISIBLE_CANDLES,
            "volume_vertices": chart_item.property("volumeVertexCount"),
            "indicator_vertices": chart_item.property("indicatorVertexCount"),
            "volume_geometry_builds": chart_item.property("volumeGeometryBuildCount"),
            "indicator_geometry_builds": chart_item.property(
                "indicatorGeometryBuildCount"
            ),
            "geometry_retained_during_pan": (
                chart_item.property("volumeGeometryBuildCount") == initial_volume_builds
                and chart_item.property("indicatorGeometryBuildCount")
                == initial_indicator_builds
            ),
            "median_camera_ms": round(statistics.median(samples), 3),
            "p95_camera_ms": round(_percentile_95(samples), 3),
            "camera_updates_per_second": round(len(samples) / elapsed_seconds, 2),
        }
        print(json.dumps(report, indent=2))
        if not report["geometry_retained_during_pan"]:
            raise SystemExit("native volume or indicator geometry rebuilt during pan")
    finally:
        view.close()
        if isValid(root_item):
            root_item.deleteLater()
        app.processEvents()


if __name__ == "__main__":
    main()
