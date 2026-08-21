r"""Native BOT-098D hybrid Backtest/OpenGL runtime probe.

Run from the Sagittarius-Engine workspace root (not under offscreen pytest):

    .\Sagittarius_Elite_Warrior\.venv\Scripts\python.exe -m \
        Sagittarius_Elite_Warrior.scripts.benchmarking.backtest_hybrid_opengl_probe

This is a deterministic local runtime guard, not a shared-CI timing gate.
"""

from __future__ import annotations

import json
import time

from PySide6.QtCore import QPointF, qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.scripts.benchmarking.backtest_chart_interaction import (
    _CANDLE_COUNT,
    _INDICATOR_COUNT,
    _MARKER_COUNT,
    _VISIBLE_CANDLES,
    _candles,
    _markers,
    _volume,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)
from sagittarius_engine.extensions.pyside_mvc import configure_app_qml

_FORBIDDEN_RENDER_MESSAGES = (
    "QQuickRenderControl",
    "Failed to begin recording a frame",
    "Failed to create context",
    "composeAndFlush",
)


def _process_for(app: QApplication, seconds: float) -> None:
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        app.processEvents()


def _sampled_color_count(view: BackTestView) -> int:
    image = view.grab().toImage()
    if image.isNull():
        return 0
    colors = {
        image.pixelColor(x, y).rgba()
        for x in range(0, image.width(), max(1, image.width() // 20))
        for y in range(0, image.height(), max(1, image.height() // 12))
    }
    return len(colors)


def main() -> None:
    messages: list[str] = []

    def capture_message(_message_type, _context, message: str) -> None:
        messages.append(message)

    previous_handler = qInstallMessageHandler(capture_message)
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    configure_app_qml(Palette.as_ui_dict(), get_icon_loader(), Palette.as_icon_dict())
    view = BackTestView()
    try:
        view.resize(1600, 1000)
        view.set_view_model(BackTestViewModel())
        view.set_chart_dev_mode(True)
        view.set_chart_opengl_enabled(True)
        card = view.render_symbol_cards(["BTCUSDT"])[0]
        view.load_qml()
        view.show()
        _process_for(app, 0.5)

        candles = _candles()
        timestamps = [row[0] for row in candles]
        card.render_historical_data(candles)
        card.render_historical_volume(_volume(candles))
        for indicator_index in range(_INDICATOR_COUNT):
            key = f"probe_ema_{indicator_index}"
            card.add_overlay_indicator(key, f"#{30 + indicator_index * 25:02x}B9F0")
            card.update_indicator_data(
                key,
                timestamps,
                [row[4] + indicator_index * 10.0 for row in candles],
            )
        markers = _markers(candles)
        card.set_script_markers("probe_trades", markers)
        _process_for(app, 0.5)

        max_start = _CANDLE_COUNT - _VISIBLE_CANDLES - 1
        for frame_index in range(60):
            start_index = frame_index * 37 % max_start
            card.plot_layout.main_plot.setXRange(
                timestamps[start_index],
                timestamps[start_index + _VISIBLE_CANDLES],
                padding=0,
            )
            scene_pos = card.plot_layout.main_plot.vb.mapViewToScene(
                QPointF(
                    timestamps[start_index + _VISIBLE_CANDLES // 2],
                    60_000.0,
                )
            )
            card.crosshair.handle_mouse_moved((scene_pos,))
            app.processEvents()

        card.clear_script_markers("probe_trades")
        app.processEvents()
        card.set_script_markers("probe_trades", markers)
        _process_for(app, 0.25)

        forbidden = [
            message
            for message in messages
            if any(token in message for token in _FORBIDDEN_RENDER_MESSAGES)
        ]
        sampled_colors = _sampled_color_count(view)
        report = {
            "qt_platform": app.platformName(),
            "requested_backend": "opengl",
            "actual_backend": card.plot_layout.render_backend,
            "fallback_reason": card.plot_layout.backend_fallback_reason,
            "candles": len(candles),
            "indicators": _INDICATOR_COUNT,
            "stored_markers": card.indicators._marker_layer.stored_marker_count(
                "probe_trades"
            ),
            "active_markers": card.indicators._marker_layer.active_marker_count(
                "probe_trades"
            ),
            "sampled_colors": sampled_colors,
            "forbidden_render_messages": forbidden,
        }
        print(json.dumps(report, indent=2))

        if card.plot_layout.render_backend != "opengl" and not (
            card.plot_layout.backend_fallback_reason
        ):
            raise SystemExit("OpenGL was neither activated nor safely rejected")
        if sampled_colors < 5:
            raise SystemExit("Hybrid frame capture is blank or visually empty")
        if forbidden:
            raise SystemExit("Hybrid render lifecycle emitted forbidden warnings")
        if len(markers) != _MARKER_COUNT:
            raise SystemExit("Probe marker fixture is incomplete")
    finally:
        for card in view.chart_cards:
            card.cleanup()
        view.close()
        view.deleteLater()
        app.processEvents()
        qInstallMessageHandler(previous_handler)


if __name__ == "__main__":
    main()
