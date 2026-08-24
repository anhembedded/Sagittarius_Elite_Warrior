"""BUG-036 regression — the benchmark's crosshair contract must be race-free.

``scripts/ci-local.ps1``'s "Chart Benchmark Contract — Python vs Native" step
compares ``crosshair_final_candle_index`` against
``expected_crosshair_candle_index``. That comparison used to read
``crosshairCandleIndex`` *after* pumping the event loop and grabbing a frame,
which let Qt Quick's synthetic frame-synchronous hover events — delivered at
the offscreen platform's phantom cursor, where no pointer exists — overwrite
the value the benchmark had just authored programmatically. The step therefore
passed or failed on byte-identical working trees depending only on machine
load, which is what this test pins down.

Runs at the Sanity tier against the real native chart plugin on purpose: the
overwrite happens inside ``NativeChartItem::hoverMoveEvent()``, so a test
double for the item cannot reach the failure path at all
(``.agents/rules/bug-fix-rule.md`` §3).
"""

from __future__ import annotations

import logging

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt, QTimer, QUrl
from PySide6.QtGui import QMouseEvent
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.scripts.benchmarking.chart_migration_benchmark import (
    drive_programmatic_crosshair_sweep,
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
        objectName: "nativeChartItem"
        anchors.fill: parent
    }
}
"""

_ITEM_WIDTH = 640.0
_ITEM_HEIGHT = 360.0
_CANDLE_COUNT = 400
_VIEWPORT_START = 100
_VIEWPORT_CANDLES = 100
# Where the offscreen platform parks its phantom cursor. Far enough from the
# swept fraction that an overwrite is unmistakable.
_PHANTOM_CURSOR = QPointF(8.0, 8.0)
# The candle NativeChartItem resolves for that phantom cursor — the value the
# overwrite used to smuggle into the CI contract.
_PHANTOM_CANDLE_INDEX = _VIEWPORT_START + int(
    _PHANTOM_CURSOR.x() / _ITEM_WIDTH * _VIEWPORT_CANDLES
)


def _snapshot_bytes():
    return pack_native_ohlcv_snapshot(
        revision=1,
        timestamps=[
            1_700_000_000_000 + index * 60_000 for index in range(_CANDLE_COUNT)
        ],
        opens=[10.0 + index for index in range(_CANDLE_COUNT)],
        highs=[12.0 + index for index in range(_CANDLE_COUNT)],
        lows=[9.0 + index for index in range(_CANDLE_COUNT)],
        closes=[11.0 + index for index in range(_CANDLE_COUNT)],
        volumes=[100.0] * _CANDLE_COUNT,
    )


def _deliver_phantom_hover(view: QQuickView) -> None:
    """Move the pointer the way Qt's delivery agent does, not by hand.

    Sending the move to the *window* is what makes this a faithful
    reproduction: it reaches the item through ``QQuickDeliveryAgent``'s real
    hover machinery, exactly like the synthetic move Qt flushes on a frame
    sync. Sending a ``QHoverEvent`` straight to the item would bypass that
    machinery and prove nothing about the delivery path.
    """
    QApplication.sendEvent(
        view,
        QMouseEvent(
            QEvent.Type.MouseMove,
            _PHANTOM_CURSOR,
            _PHANTOM_CURSOR,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        ),
    )


@pytest.fixture()
def crosshair_logs():
    """Capture the sweep's own log records, and keep them off every other handler.

    Two reasons this is a fixture and not an afterthought. First, these tests
    deliberately provoke the phantom hover, so the sweep emits a real WARNING —
    and `ci-local.ps1`'s Run Log Scan step fails the gate on any
    `- WARNING -` record in the pytest log. A test that proves the flake is
    reported must not itself trip the gate. Second, capturing the records lets
    the tests assert the report actually happened, which is the behaviour
    BUG-036 added; asserting only the returned value would let the WARNING
    silently rot away.
    """
    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Capture()
    sweep_logger = logging.getLogger("App.ChartBenchmark")
    previous_propagate = sweep_logger.propagate
    previous_level = sweep_logger.level
    sweep_logger.addHandler(handler)
    sweep_logger.propagate = False
    sweep_logger.setLevel(logging.DEBUG)
    try:
        yield records
    finally:
        sweep_logger.removeHandler(handler)
        sweep_logger.propagate = previous_propagate
        sweep_logger.setLevel(previous_level)


def _warnings_in(records: list[logging.LogRecord]) -> list[str]:
    return [
        record.getMessage() for record in records if record.levelno >= logging.WARNING
    ]


@pytest.fixture()
def native_chart(qapp):
    view = QQuickView()
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    configure_native_chart_engine(view.engine(), required=True)

    component = QQmlComponent(view.engine())
    component.setData(_QML_DOCUMENT, QUrl())
    root_item = component.create()
    assert component.errors() == []
    assert root_item is not None
    view.setContent(QUrl(), component, root_item)
    view.resize(int(_ITEM_WIDTH), int(_ITEM_HEIGHT))

    chart = root_item.findChild(type(root_item), "nativeChartItem")
    assert chart is not None
    view.show()
    QTest.qWaitForWindowExposed(view)
    qapp.processEvents()

    assert chart.submitSnapshot(_snapshot_bytes()) is True
    assert (
        chart.setViewport(
            float(_VIEWPORT_START), float(_VIEWPORT_START + _VIEWPORT_CANDLES)
        )
        is True
    )
    view.grabWindow()
    qapp.processEvents()

    # 2026-08-24: under machine load, the offscreen platform's own exposure
    # sequence (show() -> qWaitForWindowExposed() -> grabWindow()) can queue
    # its *own* phantom hover at the synthetic cursor without any test code
    # asking for one. A single processEvents() call above does not guarantee
    # that queued event has actually been dispatched yet — it can arrive late
    # and land inside the next test's sweep instead, which is exactly the
    # "stable without any phantom hover" test failing under gate load despite
    # never calling _deliver_phantom_hover() itself. Drain with a bounded
    # settle loop so fixture-setup-triggered events are fully resolved before
    # any test body starts driving its own sweep, matching the settle pattern
    # in test_native_chart_qml_plugin_sanity.py's _wait_for_property().
    for _ in range(20):
        qapp.processEvents()
        QTest.qWait(5)

    yield view, chart

    view.close()
    qapp.processEvents()


def test_crosshair_sweep_reports_the_candle_it_authored_despite_phantom_hover(
    qapp, native_chart, crosshair_logs
):
    """A hover landing after the last programmatic move must not change the gate.

    Before the fix this returned the first visible candle (the phantom cursor
    at x=8 maps there) instead of the swept fraction's candle, which is the
    exact shape of the "native final crosshair candle truth violated" failure.
    """
    view, chart = native_chart
    fraction = 0.9
    expected = _VIEWPORT_START + int(_VIEWPORT_CANDLES * fraction)

    # Fires inside the sweep's own processEvents(), i.e. in the window between
    # the last setCrosshairPosition() and the report being built.
    QTimer.singleShot(0, lambda: _deliver_phantom_hover(view))
    outcome = drive_programmatic_crosshair_sweep(
        qapp,
        view,
        chart,
        width=_ITEM_WIDTH,
        height=_ITEM_HEIGHT,
        fractions=(fraction,),
    )

    assert outcome.authored_candle_index == expected


def test_crosshair_sweep_records_a_phantom_hover_instead_of_hiding_it(
    qapp, native_chart, crosshair_logs
):
    """The overwrite still has to be visible in the report, just not decisive."""
    view, chart = native_chart
    fraction = 0.9
    expected = _VIEWPORT_START + int(_VIEWPORT_CANDLES * fraction)

    QTimer.singleShot(0, lambda: _deliver_phantom_hover(view))
    outcome = drive_programmatic_crosshair_sweep(
        qapp,
        view,
        chart,
        width=_ITEM_WIDTH,
        height=_ITEM_HEIGHT,
        fractions=(fraction,),
    )

    assert outcome.authored_candle_index == expected
    assert outcome.flushed_candle_index == _PHANTOM_CANDLE_INDEX
    assert outcome.flushed_candle_index != outcome.authored_candle_index

    # ...and it must say so out loud, or the flake is invisible again.
    warnings = _warnings_in(crosshair_logs)
    assert len(warnings) == 1
    assert "synthetic hover overwrote the crosshair" in warnings[0]
    assert str(expected) in warnings[0]
    assert str(_PHANTOM_CANDLE_INDEX) in warnings[0]


def test_crosshair_sweep_is_stable_without_any_phantom_hover(
    qapp, native_chart, crosshair_logs
):
    """Undisturbed, both readings agree — the diagnostic only fires on a real race."""
    view, chart = native_chart
    fraction = 0.5
    expected = _VIEWPORT_START + int(_VIEWPORT_CANDLES * fraction)

    outcome = drive_programmatic_crosshair_sweep(
        qapp,
        view,
        chart,
        width=_ITEM_WIDTH,
        height=_ITEM_HEIGHT,
        fractions=(fraction,),
    )

    assert outcome.authored_candle_index == expected
    assert outcome.flushed_candle_index == expected
    # No phantom writer, so nothing to report — a WARNING here would mean the
    # diagnostic cries wolf on every clean run and stops meaning anything.
    assert _warnings_in(crosshair_logs) == []


def test_crosshair_sweep_rejects_an_empty_fraction_sequence(
    qapp, native_chart, crosshair_logs
):
    """An empty sweep must not silently report the -1 'no crosshair' sentinel."""
    view, chart = native_chart

    with pytest.raises(ValueError, match="at least one fraction"):
        drive_programmatic_crosshair_sweep(
            qapp, view, chart, width=_ITEM_WIDTH, height=_ITEM_HEIGHT, fractions=()
        )
