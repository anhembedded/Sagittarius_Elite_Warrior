from __future__ import annotations

import threading

from PySide6.QtCore import QByteArray, QUrl
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickView

from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_runtime import (
    configure_native_chart_engine,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_snapshot import (
    pack_native_ohlcv_snapshot,
)

_QML_DOCUMENT = b"""
import QtQuick
import Sagittarius.NativeChart 1.0

NativeChartItem {
    objectName: "nativeChartItem"
    width: 640
    height: 360
}
"""


def _snapshot_bytes(revision: int) -> QByteArray:
    return pack_native_ohlcv_snapshot(
        revision=revision,
        timestamps=[0, 1],
        opens=[1.0, 2.0],
        highs=[2.0, 3.0],
        lows=[0.5, 1.5],
        closes=[1.5, 2.5],
        volumes=[100.0, 200.0],
    )


def test_native_chart_qml_plugin_constructs_and_enforces_snapshot_revision(qapp):
    view = QQuickView()
    configure_native_chart_engine(view.engine(), required=True)

    component = QQmlComponent(view.engine())
    component.setData(_QML_DOCUMENT, QUrl())
    root = component.create()

    assert component.errors() == []
    assert root is not None
    view.setContent(QUrl(), component, root)
    view.resize(640, 360)
    view.show()
    qapp.processEvents()

    assert root.submitSnapshot(_snapshot_bytes(revision=2)) is True
    assert root.property("snapshotRevision") == 2
    assert root.property("candleCount") == 2
    assert root.submitSnapshot(_snapshot_bytes(revision=1)) is False
    assert "increase monotonically" in root.property("lastSnapshotError")

    worker_results: list[bool] = []

    def submit_from_worker() -> None:
        worker_results.append(root.submitSnapshot(_snapshot_bytes(revision=3)))

    worker = threading.Thread(target=submit_from_worker)
    worker.start()
    worker.join()

    assert worker_results == [False]
    assert root.property("snapshotRevision") == 2

    view.close()
    root.deleteLater()
    qapp.processEvents()
