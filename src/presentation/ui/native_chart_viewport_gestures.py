"""BOT-098F6C — pure viewport math for the native chart's drag/wheel gestures.

Kept independent of QML/Qt so the actual pixel-to-candle-index arithmetic is
unit-testable without a QApplication. `NativeBacktestChart.qml` calls these
through a thin QObject bridge; it must not reimplement this math in JS.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QObject, Slot

_MIN_VISIBLE_CANDLES = 1.0
#: Matches ZoomControls._ZOOM_IN_FACTOR (chart_card/zoom_controls.py) so the
#: native wheel-zoom feel matches the existing Python renderer's.
_WHEEL_ZOOM_STEP = 0.85


def resolve_drag_viewport(
    viewport_start: float,
    viewport_end: float,
    *,
    candle_count: int,
    delta_px: float,
    width_px: float,
) -> tuple[float, float]:
    """Pans the viewport by a drag's pixel delta. A positive `delta_px`
    (dragging right) reveals earlier candles, matching pyqtgraph's own
    ViewBox drag-to-pan direction."""
    if candle_count <= 0 or width_px <= 0:
        return viewport_start, viewport_end
    span = viewport_end - viewport_start
    shift = -delta_px / width_px * span
    return _clamp_span(viewport_start + shift, viewport_end + shift, candle_count)


def resolve_wheel_viewport(
    viewport_start: float,
    viewport_end: float,
    *,
    candle_count: int,
    wheel_steps: float,
    cursor_fraction: float,
) -> tuple[float, float]:
    """Zooms the viewport around the cursor position. `wheel_steps` is a
    signed step count (positive = zoom in, one wheel notch is usually
    +-1.0); `cursor_fraction` is the pointer's position within the chart as
    a 0..1 fraction of its width, so the candle under the cursor stays
    under the cursor after zooming — the same anchor pyqtgraph's ViewBox
    uses for wheel zoom."""
    if candle_count <= 0:
        return viewport_start, viewport_end
    span = viewport_end - viewport_start
    cursor_fraction = min(1.0, max(0.0, cursor_fraction))
    anchor = viewport_start + cursor_fraction * span
    scale = _WHEEL_ZOOM_STEP**wheel_steps
    new_span = span * scale
    new_start = anchor - cursor_fraction * new_span
    new_end = new_start + new_span
    return _clamp_span(new_start, new_end, candle_count)


def _clamp_span(start: float, end: float, candle_count: int) -> tuple[float, float]:
    if not math.isfinite(start) or not math.isfinite(end):
        return 0.0, min(float(candle_count), _MIN_VISIBLE_CANDLES)

    span = min(float(candle_count), max(_MIN_VISIBLE_CANDLES, end - start))
    # Recenter on the clamped span first — a span pushed up to the minimum
    # (or down to the full candle count) must actually take effect even
    # when neither edge was ever crossed, not just when clamping an edge.
    center = (start + end) / 2.0
    start, end = center - span / 2.0, center + span / 2.0
    if start < 0.0:
        start, end = 0.0, span
    elif end > candle_count:
        start, end = candle_count - span, float(candle_count)
    return start, end


class NativeChartGestureBridge(QObject):
    """Registered as a QML context property (e.g. `gestureBridge`) so
    `NativeBacktestChart.qml`'s drag/wheel handlers call this pure math
    instead of reimplementing it in JS."""

    @Slot(float, float, int, float, float, result="QVariantList")
    def resolveDrag(
        self,
        viewport_start: float,
        viewport_end: float,
        candle_count: int,
        delta_px: float,
        width_px: float,
    ) -> list[float]:
        start, end = resolve_drag_viewport(
            viewport_start,
            viewport_end,
            candle_count=candle_count,
            delta_px=delta_px,
            width_px=width_px,
        )
        return [start, end]

    @Slot(float, float, int, float, float, result="QVariantList")
    def resolveWheel(
        self,
        viewport_start: float,
        viewport_end: float,
        candle_count: int,
        wheel_steps: float,
        cursor_fraction: float,
    ) -> list[float]:
        start, end = resolve_wheel_viewport(
            viewport_start,
            viewport_end,
            candle_count=candle_count,
            wheel_steps=wheel_steps,
            cursor_fraction=cursor_fraction,
        )
        return [start, end]
