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
        objectName: "nativeChartItem"
        anchors.fill: parent
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
        for x in range(0, rendered_image.width(), 4)
        for y in range(0, rendered_image.height(), 4)
    }


def _run_windows_visual_probe() -> None:
    app = QApplication.instance() or QApplication([])
    view, _component, root_item, root = _create_native_chart_view()
    view.show()
    app.processEvents()
    assert root.submitSnapshot(_snapshot_bytes(revision=2)) is True
    view.grabWindow()
    _wait_for_property(app, root, "renderedRevision", 2)
    assert root.setViewport(0.0, 3.0) is True
    view.grabWindow()
    _wait_for_property(
        app, root, "renderedCameraRevision", root.property("cameraRevision")
    )
    sampled_colors = _sampled_colors(view)
    assert "#00c087" in sampled_colors
    assert "#f6465d" in sampled_colors
    view.close()
    root_item.deleteLater()
    app.processEvents()


def _assert_windows_visual_probe_passes() -> None:
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "windows"
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
    assert root.property("snapshotRevision") == 2
    assert root.property("candleCount") == 5
    view.grabWindow()
    _wait_for_property(qapp, root, "renderedRevision", 2)
    assert root.property("wickVertexCount") == 10
    assert root.property("bodyVertexCount") == 30
    assert root.property("bullishCandleCount") == 4
    assert root.property("bearishCandleCount") == 1
    assert root.property("priceMinimum") == 9.0
    assert root.property("priceMaximum") == 25.0
    _assert_windows_visual_probe_passes()

    unchanged_build_count = root.property("geometryBuildCount")
    previous_camera_count = root.property("cameraUpdateCount")
    previous_camera_revision = root.property("cameraRevision")
    assert root.setViewport(0.0, 3.0) is True
    assert root.property("visiblePriceMinimum") == 9.0
    assert root.property("visiblePriceMaximum") == 13.0
    assert root.property("cameraRevision") == previous_camera_revision + 1
    assert root.property("geometryBuildCount") == unchanged_build_count
    time_ticks = root.property("timeAxisTicks")
    assert time_ticks[0]["timestampUtcMs"] == 1_700_000_000_000
    assert time_ticks[-1]["timestampUtcMs"] == 1_700_000_120_000
    assert len(root.property("priceAxisTicks")) == 5
    view.grabWindow()
    _wait_for_property(
        qapp, root, "renderedCameraRevision", previous_camera_revision + 1
    )
    assert root.property("cameraUpdateCount") == previous_camera_count + 1
    assert root.property("geometryBuildCount") == unchanged_build_count

    assert root.setViewport(float("nan"), 3.0) is False
    assert "finite and increasing" in root.property("lastViewportError")
    assert root.property("cameraRevision") == previous_camera_revision + 1
    assert root.setViewport(0.0, 3.0) is True
    assert root.property("cameraRevision") == previous_camera_revision + 1

    root.update()
    view.grabWindow()
    qapp.processEvents()
    assert root.property("geometryBuildCount") == unchanged_build_count

    view.resize(800, 400)
    view.grabWindow()
    _wait_for_property(qapp, root, "geometryBuildCount", unchanged_build_count + 1)
    assert root.submitSnapshot(_snapshot_bytes(revision=1)) is False
    assert "increase monotonically" in root.property("lastSnapshotError")
    assert root.submitSnapshot(_invalid_snapshot_bytes(revision=3)) is False
    assert "invalid OHLCV" in root.property("lastSnapshotError")
    assert root.submitSnapshot(_unordered_timestamp_snapshot_bytes(revision=3)) is False
    assert "timestamps must increase strictly" in root.property("lastSnapshotError")

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
    _run_windows_visual_probe()
