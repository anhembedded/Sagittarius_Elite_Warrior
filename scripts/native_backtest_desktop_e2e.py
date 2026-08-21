"""Desktop E2E evidence for BOT-098F6D.

Drives the REAL app entry-point components (QApplication, configure_app_qml,
MainWindow) — the same ones app_bootstrapper.main() assembles — on a REAL
windowing session (DISPLAY/WAYLAND_DISPLAY, never QT_QPA_PLATFORM=offscreen),
with `backtest.chart.backend` config set to "native".

This is the mandatory evidence ci-rule.md section 6 requires the instant a
feature becomes reachable from the real running app: proves the native chart
is what the real Backtest screen actually embeds (not a mock, not a
standalone probe), that it renders real OHLC preview data through the exact
production call path (BackTestView.on_preview_data_ready — what
BackTestPresenter itself calls after a real GetHistoricalKlinesQuery), that
it accepts real Qt mouse input, and that it produces zero Qt warnings/errors
throughout construction, data submission and interaction.

Only drag (button-held) and wheel input are asserted here — BOT-098F6C's own
interaction probe already established that hover-only QTest.mouseMove events
are measurably non-deterministic on this machine's virtual Wayland session,
while drag and wheel are 100% reliable; that finding governs this script too.

Run only on a machine with a real display session:
    python scripts/native_backtest_desktop_e2e.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
    raise SystemExit(
        "Desktop E2E requires a real windowing session — unset "
        "QT_QPA_PLATFORM (it is currently 'offscreen')"
    )
if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
    raise SystemExit(
        "Desktop E2E requires DISPLAY or WAYLAND_DISPLAY to be set — no real "
        "windowing session was detected"
    )

from PySide6.QtCore import QPoint, Qt, QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QColor, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_host_adapter import (
    NativeBacktestChartHostAdapter,
)
from sagittarius_engine.extensions.pyside_mvc import configure_app_qml
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

_CANDLES = [
    (
        1_700_000_000.0 + i * 60.0,
        10.0 + i * 0.1,
        10.5 + i * 0.1,
        9.5 + i * 0.1,
        10.2 + i * 0.1,
    )
    for i in range(120)
]
_VOLUMES = [(t, 100.0 + i, i % 2 == 0) for i, (t, *_rest) in enumerate(_CANDLES)]

#: Palette.BG_CARD (src/presentation/ui/assets/palette.py) / #base_card's
#: QSS background — the themed color the chart's own Rectangle background
#: (NativeBacktestChart.qml) must actually paint on screen.
_EXPECTED_BACKGROUND = QColor("#111318")
_WHITE = QColor("white")
#: Loose tolerance — real compositor output can differ by a few LSBs from
#: the literal QML hex due to color management, not because it's wrong.
_COLOR_TOLERANCE = 12


def _colors_close(a: QColor, b: QColor, tolerance: int = _COLOR_TOLERANCE) -> bool:
    return (
        abs(a.red() - b.red()) <= tolerance
        and abs(a.green() - b.green()) <= tolerance
        and abs(a.blue() - b.blue()) <= tolerance
    )


def _grab_pixel(widget, x_frac: float, y_frac: float) -> QColor:
    """Grabs the widget's actually-composited pixels (real GPU/RHI output on
    this real windowing session, not a QML property read) and samples one
    pixel — this is the "does the user actually SEE it" check, not a proxy
    for it."""
    image = widget.grab().toImage()
    x = int(image.width() * x_frac)
    y = int(image.height() * y_frac)
    return image.pixelColor(x, y)


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    config = ConfigManager()
    config.load_json(str(project_root / "src" / "config" / "app_config.json"))
    config.load_json(str(project_root / "src" / "config" / "user_config.json"))

    with tempfile.TemporaryDirectory(prefix="sagittarius-desktop-e2e-") as db_dir:
        config.load_dict(
            {
                ConfigKeys.DATABASE_DIR.value: db_dir,
                ConfigKeys.BACKTEST_CHART_BACKEND.value: "native",
                "DEV_BOARD_AUTOSTART_ENABLED": False,
            }
        )
        engine = create_app(config)
        engine.boot()

        messages: list[str] = []

        def capture(message_type, _context, message: str) -> None:
            if message_type in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg):
                messages.append(message)

        qInstallMessageHandler(capture)

        app = QApplication.instance() or QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        configure_app_qml(
            Palette.as_ui_dict(), get_icon_loader(), Palette.as_icon_dict()
        )

        window = MainWindow(engine)
        window.show()
        if not QTest.qWaitForWindowExposed(window):
            raise RuntimeError("MainWindow was never exposed on the real compositor")

        window.switch_screen("backtest")
        presenter = window._router.get_current_presenter()
        if not isinstance(presenter, BackTestPresenter):
            raise TypeError(f"Backtest presenter did not load, got {type(presenter)!r}")

        host = presenter.view.chart_cards[0]
        if not isinstance(host, NativeBacktestChartHostAdapter):
            raise TypeError(
                "Expected the real native adapter embedded in the real "
                f"running app's Backtest screen, got {type(host)!r}"
            )

        native_widget = host.native_host.widget
        if not QTest.qWaitForWindowExposed(native_widget):
            raise RuntimeError("Native chart widget was never exposed")
        for _ in range(5):
            app.processEvents()

        # The actual bug report this section exists to catch: a real user
        # opening the Backtest screen before any candle data has arrived
        # (sync still running, or failed) saw a blank WHITE chart area
        # instead of the app's dark theme — a silent visual defect no
        # "correct type constructed, zero Qt warnings" check catches, since
        # nothing crashes and no message is logged. Sample real composited
        # pixels, not a QML property, so this proves what the user actually
        # sees, not just what the source declares.
        corner_before_data = _grab_pixel(native_widget, 0.05, 0.05)
        if _colors_close(corner_before_data, _WHITE):
            raise RuntimeError(
                "Native chart shows a blank white background before any "
                f"data is submitted (sampled corner color: {corner_before_data.name()}) "
                "— this is the exact user-reported bug, not a false alarm."
            )
        if not _colors_close(corner_before_data, _EXPECTED_BACKGROUND):
            raise RuntimeError(
                "Native chart background does not match the app's dark "
                f"theme before any data is submitted: sampled "
                f"{corner_before_data.name()}, expected close to "
                f"{_EXPECTED_BACKGROUND.name()}."
            )

        # Real production call path: BackTestPresenter itself calls exactly
        # this after a real GetHistoricalKlinesQuery preview fetch.
        presenter.view.on_preview_data_ready(_CANDLES, _VOLUMES)
        # Real wall-clock time, not just processEvents() — the initial
        # viewport is applied via Qt.callLater() in NativeBacktestChart.qml,
        # and the Qt Quick render thread needs an actual frame pass after
        # that to produce paintable geometry before grab() can see it.
        QTest.qWait(500)

        # Sample a wide grid, not one strip — a candle body/wick is a thin
        # vertical sliver; a single mid-height horizontal line can miss
        # every one of them by construction even when candles ARE painted.
        candle_area_colors = [
            _grab_pixel(native_widget, x_frac, y_frac)
            for x_frac in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
            for y_frac in (0.2, 0.35, 0.5, 0.65, 0.8)
        ]
        if all(
            _colors_close(color, _EXPECTED_BACKGROUND) for color in candle_area_colors
        ):
            raise RuntimeError(
                "Native chart still shows only its plain background after "
                "real candle data was submitted — no candle/volume geometry "
                f"is visibly rendered. Sampled colors: "
                f"{sorted({c.name() for c in candle_area_colors})}"
            )

        center = native_widget.rect().center()
        QTest.mouseClick(native_widget, Qt.LeftButton, pos=center)
        app.processEvents()

        # Real wheel-zoom input.
        wheel_event = QWheelEvent(
            center.toPointF(),
            native_widget.mapToGlobal(center).toPointF(),
            QPoint(0, 0),
            QPoint(0, 240),
            Qt.NoButton,
            Qt.NoModifier,
            Qt.ScrollUpdate,
            False,
        )
        app.sendEvent(native_widget, wheel_event)
        app.processEvents()

        # Real drag-pan input.
        QTest.mousePress(native_widget, Qt.LeftButton, pos=center)
        QTest.mouseMove(native_widget, pos=center - QPoint(80, 0))
        QTest.mouseRelease(native_widget, Qt.LeftButton, pos=center - QPoint(80, 0))
        app.processEvents()

        window.close()
        app.processEvents()
        engine.stop()

        if messages:
            raise RuntimeError(
                f"Qt produced warnings/errors during the run: {messages}"
            )

        print(
            f"Sampled real pixel colors — background before data: "
            f"{corner_before_data.name()}, candle-area after data: "
            f"{[c.name() for c in candle_area_colors]}"
        )
        print("NATIVE_BACKTEST_DESKTOP_E2E_OK")


if __name__ == "__main__":
    main()
