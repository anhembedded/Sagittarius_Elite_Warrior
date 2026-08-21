r"""Native BOT-098E cached pan/zoom probe inside the real hybrid Backtest view.

Run from the Sagittarius-Engine workspace root:

    .\Sagittarius_Elite_Warrior\.venv\Scripts\python.exe -m \
        Sagittarius_Elite_Warrior.scripts.benchmarking.backtest_cached_interaction_hybrid_probe
"""

from __future__ import annotations

import json
import math

from PySide6.QtCore import QPoint, QPointF, Qt, qInstallMessageHandler
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.scripts.benchmarking.backtest_chart_interaction import (
    _INDICATOR_COUNT,
    _VISIBLE_CANDLES,
    _candles,
    _markers,
    _volume,
)
from Sagittarius_Elite_Warrior.scripts.benchmarking.backtest_hybrid_opengl_probe import (
    _FORBIDDEN_RENDER_MESSAGES,
    _process_for,
    _sampled_color_count,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.marker_lod import (
    marker_display_capacity,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)
from sagittarius_engine.extensions.pyside_mvc import configure_app_qml

_PAN_PIXELS = 120
_WHEEL_DELTA = 120


def _ranges_match(left: tuple[float, float], right: tuple[float, float]) -> bool:
    return all(
        math.isclose(left_value, right_value, rel_tol=0.0, abs_tol=1e-6)
        for left_value, right_value in zip(left, right)
    )


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
        view.set_chart_cached_interaction_enabled(True)
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
        card.set_script_markers("probe_trades", _markers(candles))
        card.plot_layout.main_plot.setXRange(timestamps[0], timestamps[-1], padding=0)
        _process_for(app, 0.25)
        marker_layer = card.indicators._marker_layer
        dense_marker_capacity = marker_display_capacity(
            card.plot_layout.main_plot.vb.sceneBoundingRect().width()
        )
        dense_active_markers = marker_layer.active_marker_count("probe_trades")
        dense_represented_markers = marker_layer.represented_marker_count(
            "probe_trades"
        )
        card.plot_layout.main_plot.setXRange(
            timestamps[2000],
            timestamps[2000 + _VISIBLE_CANDLES],
            padding=0,
        )
        _process_for(app, 0.25)

        controller = card.cached_interaction
        if controller is None:
            raise SystemExit("Backtest did not create cached interaction controller")
        viewport = card.plot_layout.widget.viewport()
        view_rect = card.plot_layout.main_plot.vb.sceneBoundingRect()
        pan_start = card.plot_layout.widget.mapFromScene(view_rect.center())
        pan_end = pan_start + QPoint(_PAN_PIXELS, 0)
        range_before_pan = tuple(card.plot_layout.main_plot.vb.viewRange()[0])

        QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=pan_start)
        QTest.mouseMove(viewport, pan_end)
        app.processEvents()
        pan_preview_active = controller.is_preview_active
        range_during_pan = tuple(card.plot_layout.main_plot.vb.viewRange()[0])
        pan_preview_colors = _sampled_color_count(view)
        QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=pan_end)
        app.processEvents()
        range_after_pan = tuple(card.plot_layout.main_plot.vb.viewRange()[0])

        wheel_position = QPointF(
            card.plot_layout.widget.mapFromScene(view_rect.center())
        )
        wheel_global_position = QPointF(viewport.mapToGlobal(wheel_position.toPoint()))
        range_before_zoom = tuple(card.plot_layout.main_plot.vb.viewRange()[0])
        wheel_event = QWheelEvent(
            wheel_position,
            wheel_global_position,
            QPoint(),
            QPoint(0, _WHEEL_DELTA),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        QApplication.sendEvent(viewport, wheel_event)
        app.processEvents()
        zoom_preview_active = controller.is_preview_active
        range_during_zoom = tuple(card.plot_layout.main_plot.vb.viewRange()[0])
        zoom_preview_colors = _sampled_color_count(view)
        controller.commit_zoom()
        _process_for(app, 0.1)
        range_after_zoom = tuple(card.plot_layout.main_plot.vb.viewRange()[0])

        forbidden = [
            message
            for message in messages
            if any(token in message for token in _FORBIDDEN_RENDER_MESSAGES)
        ]
        report = {
            "qt_platform": app.platformName(),
            "pan_preview_active": pan_preview_active,
            "pan_range_unchanged_during_preview": _ranges_match(
                range_before_pan, range_during_pan
            ),
            "pan_range_committed": not _ranges_match(range_before_pan, range_after_pan),
            "zoom_preview_active": zoom_preview_active,
            "zoom_range_unchanged_during_preview": _ranges_match(
                range_before_zoom, range_during_zoom
            ),
            "zoom_range_committed": not _ranges_match(
                range_before_zoom, range_after_zoom
            ),
            "pan_preview_colors": pan_preview_colors,
            "zoom_preview_colors": zoom_preview_colors,
            "dense_marker_capacity": dense_marker_capacity,
            "dense_active_markers": dense_active_markers,
            "dense_represented_markers": dense_represented_markers,
            "forbidden_render_messages": forbidden,
        }
        print(json.dumps(report, indent=2))

        if not all(
            (
                report["pan_preview_active"],
                report["pan_range_unchanged_during_preview"],
                report["pan_range_committed"],
                report["zoom_preview_active"],
                report["zoom_range_unchanged_during_preview"],
                report["zoom_range_committed"],
            )
        ):
            raise SystemExit("Cached interaction lifecycle contract failed")
        if min(pan_preview_colors, zoom_preview_colors) < 5:
            raise SystemExit("Cached interaction preview is visually empty")
        if dense_active_markers > dense_marker_capacity:
            raise SystemExit("Dense marker display exceeded its pixel budget")
        if dense_represented_markers <= dense_active_markers:
            raise SystemExit("Dense marker LOD did not preserve aggregated history")
        if forbidden:
            raise SystemExit("Hybrid render lifecycle emitted forbidden warnings")
    finally:
        for card in view.chart_cards:
            card.cleanup()
        view.close()
        view.deleteLater()
        app.processEvents()
        qInstallMessageHandler(previous_handler)


if __name__ == "__main__":
    main()
