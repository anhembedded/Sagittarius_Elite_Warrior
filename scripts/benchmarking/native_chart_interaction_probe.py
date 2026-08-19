r"""Exercise native marker/crosshair/FPS with real Qt mouse input.

Requires a real windowing session (Windows/macOS always have one; on Linux
an X11/Wayland session must actually be running — DISPLAY/WAYLAND_DISPLAY).

Run from the Sagittarius-Engine workspace root, e.g. on Windows:

    .\Sagittarius_Elite_Warrior\.venv\Scripts\python.exe -m \
        Sagittarius_Elite_Warrior.scripts.benchmarking.native_chart_interaction_probe

This is opt-in desktop evidence; shared CI remains hardware-independent.
"""

from __future__ import annotations

import json
import math
import statistics
import time

from PySide6.QtCore import (
    Q_ARG,
    Q_RETURN_ARG,
    QMetaObject,
    QPoint,
    Qt,
    QtMsgType,
    QUrl,
    qInstallMessageHandler,
)
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_marker_snapshot import (
    NativeChartMarker,
    NativeChartMarkerDirection,
    NativeChartMarkerKind,
    pack_native_marker_snapshot,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_runtime import (
    configure_native_chart_engine,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_snapshot import (
    pack_native_ohlcv_snapshot,
)

_CANDLE_COUNT = 6_420
_MARKER_COUNT = 1_200
_MOUSE_MOVES = 180
_WIDTH = 1_600
_HEIGHT = 900
_QML_DOCUMENT = b"""
import QtQuick
import Sagittarius.NativeChart 1.0

Item {
    width: 1600
    height: 900

    NativeChartItem {
        id: chart
        objectName: "nativeChartItem"
        anchors.fill: parent
        devFpsEnabled: true
    }

    Text {
        objectName: "fpsOverlay"
        anchors.right: parent.right
        text: "FPS " + nativeChart.measuredFps.toFixed(1)
        color: "white"
        visible: nativeChart.devFpsEnabled
    }

    property alias nativeChart: chart
}
"""


def _invoke_bool(item: object, method: str, *arguments: object) -> bool:
    return QMetaObject.invokeMethod(
        item,
        method,
        Qt.ConnectionType.DirectConnection,
        Q_RETURN_ARG(bool),
        *(Q_ARG(type(argument), argument) for argument in arguments),
    )


def _percentile_95(samples: list[float]) -> float:
    return sorted(samples)[math.ceil(len(samples) * 0.95) - 1]


def _snapshot():
    timestamps = [1_700_000_000_000 + index * 60_000 for index in range(_CANDLE_COUNT)]
    opens = [60_000.0 + index * 0.1 for index in range(_CANDLE_COUNT)]
    closes = [
        value + math.sin(index / 11.0) * 10.0 for index, value in enumerate(opens)
    ]
    snapshot = pack_native_ohlcv_snapshot(
        revision=1,
        timestamps=timestamps,
        opens=opens,
        highs=[
            max(open_, close) + 5.0 for open_, close in zip(opens, closes, strict=True)
        ],
        lows=[
            min(open_, close) - 5.0 for open_, close in zip(opens, closes, strict=True)
        ],
        closes=closes,
        volumes=[10.0 + index % 100 for index in range(_CANDLE_COUNT)],
    )
    markers = tuple(
        NativeChartMarker(
            candle_index=index * 5,
            price=closes[index * 5],
            rgba=(0xFF00C087 if index % 2 == 0 else 0xFFF6465D),
            kind=(
                NativeChartMarkerKind.LONG_ENTRY
                if index % 2 == 0
                else NativeChartMarkerKind.LONG_EXIT
            ),
            direction=(
                NativeChartMarkerDirection.UP
                if index % 2 == 0
                else NativeChartMarkerDirection.DOWN
            ),
        )
        for index in range(_MARKER_COUNT)
    )
    return snapshot, pack_native_marker_snapshot(
        revision=1,
        candle_count=_CANDLE_COUNT,
        markers=markers,
    )


def main() -> None:
    messages: list[str] = []

    def capture_message(message_type, _context, message: str) -> None:
        if message_type in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg):
            messages.append(message)

    previous_handler = qInstallMessageHandler(capture_message)
    app = QApplication.instance() or QApplication([])
    view = QQuickView()
    root_item = None
    try:
        view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        configure_native_chart_engine(view.engine(), required=True)
        component = QQmlComponent(view.engine())
        component.setData(_QML_DOCUMENT, QUrl())
        root_item = component.create()
        if component.errors() or root_item is None:
            raise RuntimeError("native interaction QML did not construct")
        view.setContent(QUrl(), component, root_item)
        view.resize(_WIDTH, _HEIGHT)
        chart = root_item.findChild(type(root_item), "nativeChartItem")
        if chart is None:
            raise RuntimeError("native chart item was not found")
        view.show()
        # Wait for the window's real first expose/paint to settle before
        # taking any measurement. Without this, the deferred initial paint
        # can land mid-interaction-loop and get misattributed as a
        # pointer-triggered geometry rebuild.
        QTest.qWaitForWindowExposed(view)
        app.processEvents()
        snapshot, marker_snapshot = _snapshot()
        if not _invoke_bool(chart, "submitSnapshot", snapshot):
            raise RuntimeError(chart.property("lastSnapshotError"))
        if not _invoke_bool(chart, "submitMarkerSnapshot", marker_snapshot):
            raise RuntimeError(chart.property("lastMarkerSnapshotError"))
        view.grabWindow()
        # The scene graph's render thread can take a few extra event-loop
        # turns to finish flushing the initial frame after the first grab.
        for _ in range(20):
            app.processEvents()
        baseline = {
            "ohlcv": chart.property("geometryBuildCount"),
            "volume": chart.property("volumeGeometryBuildCount"),
            "indicator": chart.property("indicatorGeometryBuildCount"),
            "marker": chart.property("markerGeometryBuildCount"),
        }

        # The window manager/compositor — not the app — has final say on the
        # actual window size (e.g. Wayland routinely grants a smaller size
        # than requested). Use the real size so synthetic moves always land
        # inside the window instead of firing "outside target window" noise.
        actual_width = view.width()
        actual_height = view.height()

        samples: list[float] = []
        for move_index in range(_MOUSE_MOVES):
            x = 1 + move_index * (actual_width - 2) // (_MOUSE_MOVES - 1)
            y = actual_height // 3 + move_index % 120
            started = time.perf_counter()
            QTest.mouseMove(view, QPoint(x, y), 4)
            app.processEvents()
            view.grabWindow()
            samples.append((time.perf_counter() - started) * 1000.0)

        retained = {
            "ohlcv": chart.property("geometryBuildCount") == baseline["ohlcv"],
            "volume": chart.property("volumeGeometryBuildCount") == baseline["volume"],
            "indicator": chart.property("indicatorGeometryBuildCount")
            == baseline["indicator"],
            "marker": chart.property("markerGeometryBuildCount") == baseline["marker"],
        }
        report = {
            "qt_platform": app.platformName(),
            "mouse_moves": _MOUSE_MOVES,
            "candles": _CANDLE_COUNT,
            "markers": _MARKER_COUNT,
            "displayed_markers": chart.property("displayedMarkerCount"),
            "represented_markers": chart.property("representedMarkerCount"),
            "median_interaction_ms": round(statistics.median(samples), 3),
            "p95_interaction_ms": round(_percentile_95(samples), 3),
            "measured_completed_frame_fps": round(chart.property("measuredFps"), 2),
            "crosshair_visible": chart.property("crosshairVisible"),
            "crosshair_candle_index": chart.property("crosshairCandleIndex"),
            "bulk_geometry_retained": retained,
            "qt_warning_count": len(messages),
        }
        print(json.dumps(report, indent=2))
        if not report["crosshair_visible"] or not all(retained.values()):
            raise SystemExit("native pointer interaction violated retained geometry")
        if report["measured_completed_frame_fps"] <= 0.0:
            raise SystemExit("dev FPS did not observe completed frames")
        if messages:
            raise SystemExit("Qt warnings: " + " | ".join(messages))
    finally:
        view.close()
        if root_item is not None and isValid(root_item):
            root_item.deleteLater()
        app.processEvents()
        qInstallMessageHandler(previous_handler)


if __name__ == "__main__":
    main()
