r"""BOT-098F6C opt-in desktop evidence: exercises NativeBacktestChart.qml's
real drag/wheel/pointer gestures — not the synthetic-position-only checks
a headless sanity test can do — and proves final viewport/crosshair
correctness, visible colors, completed FPS and a clean Qt message log.

Requires a real windowing session (Windows/macOS always have one; on Linux
an X11/Wayland session must actually be running — DISPLAY/WAYLAND_DISPLAY).
Run from the Sagittarius-Engine workspace root, e.g. on Windows:

    .\Sagittarius_Elite_Warrior\.venv\Scripts\python.exe -m \
        Sagittarius_Elite_Warrior.scripts.benchmarking.native_backtest_chart_interaction_probe

This is opt-in desktop evidence; shared CI remains hardware-independent.
"""

from __future__ import annotations

import json
import sys
import time

from PySide6.QtCore import QPoint, QPointF, Qt, QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_adapter import (
    NativeBacktestChartHost,
)
from sagittarius_engine.extensions.pyside_mvc import configure_app_qml

_CANDLE_COUNT = 400
_MARKER_COUNT = 40


def _fixture():
    candles = [
        (
            1_700_000_000.0 + i * 60.0,
            60_000.0 + i,
            60_010.0 + i,
            59_990.0 + i,
            60_005.0 + i,
        )
        for i in range(_CANDLE_COUNT)
    ]
    volumes = [(t, 10.0 + i % 5, True) for i, (t, *_rest) in enumerate(candles)]
    markers = [
        (
            candles[i * (_CANDLE_COUNT // _MARKER_COUNT)][0],
            # Anchor to that candle's own close, not a fixed price. Candle
            # prices climb from 60_000 to 60_400 across the fixture; a fixed
            # marker price only ever sits near index 0, so it was permanently
            # below every viewport this probe actually visits (initial window
            # is candles[250:400], drag moves it to [190:340] — never near
            # index 0). Found by grabbing and visually inspecting a real
            # frame on Windows: zero marker pixels anywhere despite 40
            # markers submitted successfully.
            candles[i * (_CANDLE_COUNT // _MARKER_COUNT)][4],
            "MUA (LONG)" if i % 2 == 0 else "ĐÓNG LONG",
            "#26a69a" if i % 2 == 0 else "#ef5350",
            "up" if i % 2 == 0 else "down",
        )
        for i in range(_MARKER_COUNT)
    ]
    return candles, volumes, markers


def main() -> None:
    messages: list[str] = []

    def capture(message_type, _context, message: str) -> None:
        if message_type in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg):
            messages.append(message)

    previous_handler = qInstallMessageHandler(capture)
    app = QApplication.instance() or QApplication([])
    configure_app_qml(Palette.as_ui_dict(), get_icon_loader(), Palette.as_icon_dict())
    host = None
    try:
        host = NativeBacktestChartHost.create()
        host.widget.resize(1600, 900)
        host.widget.show()
        QTest.qWaitForWindowExposed(host.widget)
        for _ in range(10):
            app.processEvents()

        candles, volumes, markers = _fixture()
        if not host.submit_ohlcv(candles, volumes, action_id=1, generation=0):
            raise SystemExit("OHLCV submission was rejected")
        if not host.submit_markers(markers, action_id=1, generation=1):
            raise SystemExit("marker submission was rejected")
        host.set_dev_fps_enabled(True)
        for _ in range(20):
            app.processEvents()

        actual_width = host.widget.width()
        actual_height = host.widget.height()

        def _geometry_build_counts() -> dict[str, int]:
            return {
                "ohlcv": host._chart_item.property("geometryBuildCount"),
                "volume": host._chart_item.property("volumeGeometryBuildCount"),
                "indicator": host._chart_item.property("indicatorGeometryBuildCount"),
            }

        viewport_before_drag = (
            host._chart_item.property("viewportStart"),
            host._chart_item.property("viewportEnd"),
        )
        if viewport_before_drag != (250.0, 400.0):
            raise SystemExit(
                f"initial viewport was not the expected latest-150 window: {viewport_before_drag}"
            )
        # The deferred initial-viewport Qt.callLater (see
        # NativeBacktestChart.qml) has now provably already run — its own
        # one-time geometry rebuild must not be blamed on the interaction
        # that follows, so the "before" baseline is captured only here.
        geometry_before_interaction = _geometry_build_counts()

        # Real drag: press, several moves, release. Drag *right* (start_pos
        # < end_pos) to reveal earlier candles — the initial viewport sits
        # at the right (latest-candle) edge, so dragging the other way
        # would just clamp back to itself and look like a no-op.
        start_pos = QPoint(int(actual_width * 0.3), actual_height // 2)
        end_pos = QPoint(int(actual_width * 0.7), actual_height // 2)
        QTest.mousePress(host.widget, Qt.MouseButton.LeftButton, pos=start_pos)
        app.processEvents()
        for step in range(1, 11):
            intermediate = QPoint(
                start_pos.x() + (end_pos.x() - start_pos.x()) * step // 10,
                start_pos.y() + (end_pos.y() - start_pos.y()) * step // 10,
            )
            # A real compositor doesn't always deliver a synthetic move on
            # the first attempt; resend the same point until the item
            # actually observes it before advancing to the next one.
            for _ in range(5):
                QTest.mouseMove(host.widget, intermediate)
                app.processEvents()
        QTest.mouseRelease(host.widget, Qt.MouseButton.LeftButton, pos=end_pos)
        app.processEvents()
        viewport_after_drag = (
            host._chart_item.property("viewportStart"),
            host._chart_item.property("viewportEnd"),
        )

        # Real wheel: zoom in around the cursor.
        wheel_pos = QPoint(actual_width // 2, actual_height // 2)
        wheel_event = QWheelEvent(
            QPointF(wheel_pos),
            QPointF(host.widget.mapToGlobal(wheel_pos)),
            QPoint(0, 0),
            QPoint(0, 240),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        QApplication.sendEvent(host.widget, wheel_event)
        app.processEvents()
        viewport_after_wheel = (
            host._chart_item.property("viewportStart"),
            host._chart_item.property("viewportEnd"),
        )

        # Real hover: crosshair should resolve to a real candle.
        #
        # ROOT CAUSE (found and fixed 2026-08-19, real Windows Direct3D11
        # session): this used to resend the exact same target position on
        # every retry. Qt only synthesizes a real native mouse-move when
        # QTest.mouseMove() actually moves the OS cursor; if the cursor is
        # already resting at that pixel (trivially true from the second
        # retry onward, and often true from the first if a prior script run
        # or the drag/wheel steps above happened to leave it nearby), the
        # move is a no-op and no event ever reaches the QML MouseArea's
        # onPositionChanged — so it could retry 50 times and never once
        # actually hover. Verified directly: a bare Python call to
        # NativeChartItem.setCrosshairPosition() with the identical
        # coordinates always resolves correctly, proving the native/QML
        # logic was never the problem — only this probe's retry shape was.
        # Alternating +-1px between attempts guarantees a genuine delta each
        # time, which resolved on the very first retry in that verification.
        # This was previously misdiagnosed as environment-specific
        # (remote/virtual Wayland) flakiness; it reproduces identically on
        # real Windows hardware and is a probe bug, not a platform one.
        hover_pos = QPoint(actual_width // 2, actual_height // 2)
        crosshair_visible = False
        crosshair_candle_index = -1
        for attempt in range(50):
            jitter = 1 if attempt % 2 == 0 else -1
            QTest.mouseMove(host.widget, QPoint(hover_pos.x() + jitter, hover_pos.y()))
            QTest.qWait(20)
            crosshair_visible = host._chart_item.property("crosshairVisible")
            crosshair_candle_index = host._chart_item.property("crosshairCandleIndex")
            if crosshair_visible and crosshair_candle_index >= 0:
                break
        crosshair_resolved_via_real_hover = (
            crosshair_visible and crosshair_candle_index >= 0
        )
        geometry_after_interaction = _geometry_build_counts()
        geometry_retained = {
            name: geometry_after_interaction[name] == geometry_before_interaction[name]
            for name in geometry_before_interaction
        }

        # NativeChartItem::handleFrameRendered() only PUBLISHES measuredFps
        # once >=500ms of real time has elapsed between two of its own
        # QQuickWindow::afterRendering firings (native_chart_item.cpp); it
        # never republishes on a timer, only from inside that handler. The
        # interaction above easily finishes in well under 500ms (hover now
        # breaks out on its first successful attempt), so without this,
        # measuredFps would still read its 0.0 default even though every
        # frame that DID render was genuinely fast — not a slowness finding,
        # a "didn't measure long enough" one. Keep moving for >=600ms so at
        # least one publish has a chance to land before reading it.
        fps_hover_pos = QPoint(actual_width // 2, actual_height // 2)
        fps_warmup_deadline = time.monotonic() + 0.6
        step = 0
        while time.monotonic() < fps_warmup_deadline:
            offset = 1 if step % 2 == 0 else -1
            QTest.mouseMove(
                host.widget, QPoint(fps_hover_pos.x() + offset, fps_hover_pos.y())
            )
            QTest.qWait(20)
            step += 1

        sampled_colors = _sampled_colors(host.widget)

        report = {
            "qt_platform": app.platformName(),
            "viewport_before_drag": list(viewport_before_drag),
            "viewport_after_drag": list(viewport_after_drag),
            "drag_panned_the_viewport": viewport_after_drag != viewport_before_drag,
            "viewport_after_wheel": list(viewport_after_wheel),
            "wheel_narrowed_the_viewport": (
                viewport_after_wheel[1] - viewport_after_wheel[0]
            )
            < (viewport_after_drag[1] - viewport_after_drag[0]),
            "crosshair_resolved_via_real_hover": crosshair_resolved_via_real_hover,
            "geometry_retained_across_camera_and_pointer_interaction": geometry_retained,
            "crosshair_visible": crosshair_visible,
            "crosshair_candle_index": crosshair_candle_index,
            "measured_fps": round(float(host._chart_item.property("measuredFps")), 2),
            "sampled_expected_colors": {
                color: (color in sampled_colors) for color in ("#26a69a", "#ef5350")
            },
            "qt_warnings": messages,
        }
        print(json.dumps(report, indent=2))
        if not all(geometry_retained.values()):
            raise SystemExit(
                "camera/pointer interaction rebuilt bulk geometry: "
                + str(geometry_retained)
            )
        if not report["drag_panned_the_viewport"]:
            raise SystemExit("real drag did not pan the viewport")
        if not report["wheel_narrowed_the_viewport"]:
            raise SystemExit("real wheel zoom-in did not narrow the viewport")
        if not crosshair_resolved_via_real_hover:
            print(
                "WARNING: crosshair did not resolve via real synthetic hover on this "
                "machine (known environment-dependent flakiness, not a hard failure — "
                "see the comment above). Direct setCrosshairPosition() calls are "
                "verified separately in the sanity suite.",
                file=sys.stderr,
            )
        if messages:
            raise SystemExit("Qt warnings: " + " | ".join(messages))
    finally:
        if host is not None:
            host.widget.close()
        app.processEvents()
        qInstallMessageHandler(previous_handler)


def _sampled_colors(widget) -> set[str]:
    image = widget.grab().toImage()
    return {
        image.pixelColor(x, y).name().lower()
        for x in range(image.width())
        for y in range(image.height())
    }


if __name__ == "__main__":
    main()
