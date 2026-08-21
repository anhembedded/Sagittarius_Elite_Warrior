from __future__ import annotations

import os
import struct
import subprocess
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QByteArray, QUrl
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_indicator_snapshot import (
    NativeIndicatorSeries,
    pack_native_indicator_snapshot,
)
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

_QML_DOCUMENT = b"""
import QtQuick
import Sagittarius.NativeChart 1.0

Item {
    width: 640
    height: 360

    NativeChartItem {
        id: chart
        objectName: "nativeChartItem"
        anchors.fill: parent
    }

    Text {
        objectName: "crosshairTooltip"
        visible: chart.crosshairVisible
        text: chart.crosshairTooltip.candleIndex + ":" + chart.crosshairTooltip.close
        color: "white"
    }

    Text {
        objectName: "devFpsOverlay"
        visible: chart.devFpsEnabled
        text: "FPS " + chart.measuredFps.toFixed(1)
        color: "white"
    }
}
"""


def _snapshot_bytes(revision: int) -> QByteArray:
    return pack_native_ohlcv_snapshot(
        revision=revision,
        timestamps=[
            1_700_000_000_000,
            1_700_000_060_000,
            1_700_000_120_000,
            1_700_000_180_000,
            1_700_000_240_000,
        ],
        opens=[10.0, 12.0, 11.0, 20.0, 22.0],
        highs=[13.0, 13.0, 12.0, 21.0, 25.0],
        lows=[9.0, 9.0, 10.0, 19.0, 21.0],
        closes=[12.0, 10.0, 11.0, 20.0, 24.0],
        volumes=[100.0, 200.0, 150.0, 90.0, 220.0],
    )


def _invalid_snapshot_bytes(revision: int) -> QByteArray:
    return pack_native_ohlcv_snapshot(
        revision=revision,
        timestamps=[0],
        opens=[10.0],
        highs=[9.0],
        lows=[8.0],
        closes=[10.0],
        volumes=[100.0],
    )


def _indicator_snapshot_bytes(revision: int) -> QByteArray:
    return pack_native_indicator_snapshot(
        revision=revision,
        candle_count=5,
        series=(
            NativeIndicatorSeries(
                rgba=0xFF00BFFF,
                values=(11.0, 11.5, 10.5, 19.5, 23.0),
            ),
            NativeIndicatorSeries(
                rgba=0xFFF0B90B,
                values=(10.5, 11.0, 10.75, 20.0, 22.5),
            ),
        ),
    )


def _misaligned_indicator_snapshot_bytes(revision: int) -> QByteArray:
    return pack_native_indicator_snapshot(
        revision=revision,
        candle_count=4,
        series=(NativeIndicatorSeries(rgba=0xFF00BFFF, values=(1.0, 2.0, 3.0, 4.0)),),
    )


def _marker_snapshot_bytes(revision: int) -> QByteArray:
    return pack_native_marker_snapshot(
        revision=revision,
        candle_count=5,
        markers=(
            NativeChartMarker(
                candle_index=1,
                price=9.5,
                rgba=0xFF00C087,
                kind=NativeChartMarkerKind.LONG_ENTRY,
                direction=NativeChartMarkerDirection.UP,
            ),
            NativeChartMarker(
                candle_index=2,
                price=11.5,
                rgba=0xFFF6465D,
                kind=NativeChartMarkerKind.LONG_EXIT,
                direction=NativeChartMarkerDirection.DOWN,
            ),
        ),
    )


def _misaligned_marker_snapshot_bytes(revision: int) -> QByteArray:
    return pack_native_marker_snapshot(
        revision=revision,
        candle_count=4,
        markers=(
            NativeChartMarker(
                candle_index=1,
                price=10.0,
                rgba=0xFF00C087,
                kind=NativeChartMarkerKind.LONG_ENTRY,
                direction=NativeChartMarkerDirection.UP,
            ),
        ),
    )


def _non_finite_marker_snapshot_bytes(revision: int) -> QByteArray:
    packed = bytearray(_marker_snapshot_bytes(revision))
    struct.pack_into("<d", packed, 40, float("nan"))
    return QByteArray(bytes(packed))


def _non_finite_indicator_snapshot_bytes(revision: int) -> QByteArray:
    packed = bytearray(_indicator_snapshot_bytes(revision))
    indicator_values_offset = 32 + 2 * 4
    struct.pack_into("<d", packed, indicator_values_offset, float("nan"))
    return QByteArray(bytes(packed))


def _unordered_timestamp_snapshot_bytes(revision: int) -> QByteArray:
    packed = bytearray(
        pack_native_ohlcv_snapshot(
            revision=revision,
            timestamps=[1, 2],
            opens=[10.0, 10.0],
            highs=[11.0, 11.0],
            lows=[9.0, 9.0],
            closes=[10.0, 10.0],
            volumes=[100.0, 100.0],
        )
    )
    struct.pack_into("<q", packed, 32, 1)
    return QByteArray(bytes(packed))


def _wait_for_property(qapp, item, name: str, expected) -> None:
    for _ in range(50):
        qapp.processEvents()
        if item.property(name) == expected:
            return
        QTest.qWait(10)
    assert item.property(name) == expected


def _create_native_chart_view():
    view = QQuickView()
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    configure_native_chart_engine(view.engine(), required=True)

    component = QQmlComponent(view.engine())
    component.setData(_QML_DOCUMENT, QUrl())
    root_item = component.create()
    assert component.errors() == []
    assert root_item is not None

    view.setContent(QUrl(), component, root_item)
    view.resize(640, 360)
    root = root_item.findChild(type(root_item), "nativeChartItem")
    assert root is not None
    return view, component, root_item, root


def _sampled_colors(view: QQuickView) -> set[str]:
    rendered_image = view.grabWindow()
    return {
        rendered_image.pixelColor(x, y).name().lower()
        for x in range(rendered_image.width())
        for y in range(rendered_image.height())
    }


def _has_real_display() -> bool:
    """True when a real (non-offscreen) windowing session is available.

    Windows and macOS always have a compositor, headless or not. Linux only
    has one when an X11/Wayland session is actually running (DISPLAY /
    WAYLAND_DISPLAY), which is not the case on typical headless CI runners.
    """
    if sys.platform.startswith("win") or sys.platform == "darwin":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _run_real_display_visual_probe() -> None:
    app = QApplication.instance() or QApplication([])
    view, _component, root_item, root = _create_native_chart_view()
    view.show()
    app.processEvents()
    assert root.submitSnapshot(_snapshot_bytes(revision=2)) is True
    assert root.submitIndicatorSnapshot(_indicator_snapshot_bytes(revision=2)) is True
    assert root.submitMarkerSnapshot(_marker_snapshot_bytes(revision=2)) is True
    view.grabWindow()
    _wait_for_property(app, root, "renderedRevision", 2)
    _wait_for_property(app, root, "indicatorVertexCount", 10)
    assert root.setViewport(0.0, 3.0) is True
    view.grabWindow()
    _wait_for_property(
        app, root, "renderedCameraRevision", root.property("cameraRevision")
    )
    sampled_colors = _sampled_colors(view)
    assert "#00c087" in sampled_colors
    assert "#f6465d" in sampled_colors
    assert "#00bfff" in sampled_colors
    assert "#f0b90b" in sampled_colors
    view.close()
    root_item.deleteLater()
    app.processEvents()


def _assert_real_display_visual_probe_passes() -> None:
    environment = os.environ.copy()
    # Drop any inherited "offscreen" override so Qt auto-selects the real
    # backend for this host (windows/cocoa/xcb/wayland) instead of faking it.
    environment.pop("QT_QPA_PLATFORM", None)
    package_root = str(Path(__file__).resolve().parents[3])
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (package_root, environment.get("PYTHONPATH", "")) if value
    )
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--visual-probe"],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_native_chart_qml_plugin_constructs_and_enforces_snapshot_revision(qapp):
    view, _component, root_item, root = _create_native_chart_view()
    view.show()
    qapp.processEvents()

    assert root.submitSnapshot(_snapshot_bytes(revision=2)) is True
    assert root.submitIndicatorSnapshot(_indicator_snapshot_bytes(revision=2)) is True
    assert root.submitMarkerSnapshot(_marker_snapshot_bytes(revision=2)) is True
    assert root.property("snapshotRevision") == 2
    assert root.property("candleCount") == 5
    assert root.property("indicatorSnapshotRevision") == 2
    assert root.property("indicatorSeriesCount") == 2
    assert root.property("markerSnapshotRevision") == 2
    assert root.property("markerCount") == 2
    view.grabWindow()
    _wait_for_property(qapp, root, "renderedRevision", 2)
    assert root.property("wickVertexCount") == 10
    assert root.property("bodyVertexCount") == 30
    assert root.property("volumeVertexCount") == 30
    assert root.property("indicatorVertexCount") == 10
    _wait_for_property(qapp, root, "markerVertexCount", 6)
    assert root.property("displayedMarkerCount") == 2
    assert root.property("representedMarkerCount") == 2
    assert root.property("indicatorPixelColumnCount") >= 1
    assert root.property("renderDevicePixelRatio") >= 1.0
    assert root.property("bullishCandleCount") == 4
    assert root.property("bearishCandleCount") == 1
    assert root.property("priceMinimum") == 9.0
    assert root.property("priceMaximum") == 25.0
    # Real-backend visual evidence needs an actual windowing session; skip
    # cleanly on headless CI runners instead of assuming Windows-only.
    if _has_real_display():
        _assert_real_display_visual_probe_passes()

    unchanged_build_count = root.property("geometryBuildCount")
    unchanged_volume_build_count = root.property("volumeGeometryBuildCount")
    unchanged_indicator_build_count = root.property("indicatorGeometryBuildCount")
    unchanged_marker_build_count = root.property("markerGeometryBuildCount")
    previous_camera_count = root.property("cameraUpdateCount")
    previous_camera_revision = root.property("cameraRevision")
    assert root.setViewport(0.0, 3.0) is True
    assert root.property("visiblePriceMinimum") == 9.0
    assert root.property("visiblePriceMaximum") == 13.0
    assert root.property("cameraRevision") == previous_camera_revision + 1
    assert root.property("geometryBuildCount") == unchanged_build_count
    assert root.property("volumeGeometryBuildCount") == unchanged_volume_build_count
    assert (
        root.property("indicatorGeometryBuildCount") == unchanged_indicator_build_count
    )
    assert root.property("markerGeometryBuildCount") == unchanged_marker_build_count
    view.grabWindow()
    _wait_for_property(
        qapp, root, "renderedCameraRevision", previous_camera_revision + 1
    )
    time_ticks = root.property("timeAxisTicks")
    assert time_ticks[0]["timestampUtcMs"] == 1_700_000_000_000
    assert time_ticks[-1]["timestampUtcMs"] == 1_700_000_120_000
    assert len(root.property("priceAxisTicks")) == 5
    assert root.property("cameraUpdateCount") == previous_camera_count + 1

    assert root.setViewport(1.0, 4.0) is True
    view.grabWindow()
    _wait_for_property(
        qapp, root, "renderedCameraRevision", previous_camera_revision + 2
    )
    assert root.property("volumeGeometryBuildCount") == unchanged_volume_build_count
    assert (
        root.property("indicatorGeometryBuildCount") == unchanged_indicator_build_count
    )
    assert root.property("cameraUpdateCount") == previous_camera_count + 2
    assert root.property("geometryBuildCount") == unchanged_build_count
    unchanged_marker_build_count = root.property("markerGeometryBuildCount")

    assert root.setCrosshairPosition(320.0, 180.0) is True
    view.grabWindow()
    _wait_for_property(qapp, root, "crosshairVisible", True)
    assert root.property("crosshairCandleIndex") == 2
    tooltip = root.property("crosshairTooltip")
    assert tooltip["timestampUtcMs"] == 1_700_000_120_000
    assert tooltip["open"] == 11.0
    assert tooltip["close"] == 11.0
    assert root.property("geometryBuildCount") == unchanged_build_count
    assert root.property("volumeGeometryBuildCount") == unchanged_volume_build_count
    assert (
        root.property("indicatorGeometryBuildCount") == unchanged_indicator_build_count
    )
    assert root.property("markerGeometryBuildCount") == unchanged_marker_build_count

    for pointer_x in range(0, 640, 32):
        assert root.setCrosshairPosition(float(pointer_x), 120.0) is True
        view.grabWindow()
    assert root.property("geometryBuildCount") == unchanged_build_count
    assert root.property("volumeGeometryBuildCount") == unchanged_volume_build_count
    assert (
        root.property("indicatorGeometryBuildCount") == unchanged_indicator_build_count
    )
    assert root.property("markerGeometryBuildCount") == unchanged_marker_build_count
    root.clearCrosshair()
    assert root.property("crosshairVisible") is False

    assert root.setViewport(float("nan"), 3.0) is False
    assert "finite and increasing" in root.property("lastViewportError")
    assert root.property("cameraRevision") == previous_camera_revision + 2
    assert root.setViewport(0.0, 3.0) is True
    assert root.property("cameraRevision") == previous_camera_revision + 3

    root.update()
    view.grabWindow()
    qapp.processEvents()
    assert root.property("geometryBuildCount") == unchanged_build_count

    view.resize(800, 400)
    view.grabWindow()
    _wait_for_property(qapp, root, "geometryBuildCount", unchanged_build_count + 1)
    _wait_for_property(
        qapp, root, "volumeGeometryBuildCount", unchanged_volume_build_count + 1
    )
    _wait_for_property(
        qapp,
        root,
        "indicatorGeometryBuildCount",
        unchanged_indicator_build_count + 1,
    )
    assert root.submitSnapshot(_snapshot_bytes(revision=1)) is False
    assert "increase monotonically" in root.property("lastSnapshotError")
    assert root.submitSnapshot(_invalid_snapshot_bytes(revision=3)) is False
    assert "invalid OHLCV" in root.property("lastSnapshotError")
    assert root.submitSnapshot(_unordered_timestamp_snapshot_bytes(revision=3)) is False
    assert "timestamps must increase strictly" in root.property("lastSnapshotError")
    assert root.submitIndicatorSnapshot(_indicator_snapshot_bytes(revision=1)) is False
    assert "increase monotonically" in root.property("lastIndicatorSnapshotError")
    assert (
        root.submitIndicatorSnapshot(_misaligned_indicator_snapshot_bytes(revision=3))
        is False
    )
    assert "align with the active candle count" in root.property(
        "lastIndicatorSnapshotError"
    )
    assert (
        root.submitIndicatorSnapshot(_non_finite_indicator_snapshot_bytes(revision=3))
        is False
    )
    assert "values must be finite" in root.property("lastIndicatorSnapshotError")
    assert root.submitMarkerSnapshot(_marker_snapshot_bytes(revision=1)) is False
    assert "increase monotonically" in root.property("lastMarkerSnapshotError")
    assert root.submitMarkerSnapshot(_misaligned_marker_snapshot_bytes(3)) is False
    assert "align with the active candle count" in root.property(
        "lastMarkerSnapshotError"
    )
    assert root.submitMarkerSnapshot(_non_finite_marker_snapshot_bytes(3)) is False
    assert "price must be finite" in root.property("lastMarkerSnapshotError")

    worker_results: list[bool] = []

    def submit_from_worker() -> None:
        worker_results.append(root.submitSnapshot(_snapshot_bytes(revision=3)))

    worker = threading.Thread(target=submit_from_worker)
    worker.start()
    worker.join()

    assert worker_results == [False]
    assert root.property("snapshotRevision") == 2

    view.close()
    root_item.deleteLater()
    qapp.processEvents()


if __name__ == "__main__" and "--visual-probe" in sys.argv:
    _run_real_display_visual_probe()
