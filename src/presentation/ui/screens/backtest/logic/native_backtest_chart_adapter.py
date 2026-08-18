"""BOT-098F6B — native chart adapter and snapshot contract for Backtest.

Converts Backtest's Python data (UTC-second klines, timestamp-keyed
indicator samples, timestamp-based trade markers) into the immutable native
snapshot ABIs already used by the F4 marker/crosshair work and the F5
benchmark, and constructs a `NativeChartItem` inside an embedded
`QQuickWidget`. Not selected by any production factory in this phase
(BOT-098F6D wires that later) — this module only proves the seam works.
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, QUrl
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuickWidgets import QQuickWidget

from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.chart_card import (
    OhlcCandle,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.marker_layer import (
    MarkerPoint,
)
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
    NativeChartRuntimeError,
    configure_native_chart_engine,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_snapshot import (
    pack_native_ohlcv_snapshot,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_timezone_bridge import (
    NativeChartTimezoneBridge,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_viewport_gestures import (
    NativeChartGestureBridge,
)
from sagittarius_engine.extensions.pyside_mvc import create_quick_widget

_MARKER_LABEL_TO_KIND: dict[str, NativeChartMarkerKind] = {
    "MUA (LONG)": NativeChartMarkerKind.LONG_ENTRY,
    "ĐÓNG LONG": NativeChartMarkerKind.LONG_EXIT,
    "BÁN (SHORT)": NativeChartMarkerKind.SHORT_ENTRY,
    "ĐÓNG SHORT": NativeChartMarkerKind.SHORT_EXIT,
}
_MARKER_DIRECTION_STR_TO_ENUM: dict[str, NativeChartMarkerDirection] = {
    "up": NativeChartMarkerDirection.UP,
    "down": NativeChartMarkerDirection.DOWN,
}

#: BOT-098F6C's declarative wrapper: axis ticks, crosshair tooltip, dev FPS
#: and real drag/wheel/pointer gesture handling around the bare NativeChartItem.
_NATIVE_CHART_QML_PATH = Path(__file__).resolve().parents[1] / "NativeBacktestChart.qml"


def timestamp_seconds_to_ms(timestamp_seconds: float) -> int:
    """Backtest klines/markers carry UTC-second floats; the native ABI is
    strict UTC-millisecond int64. Round rather than truncate so a value
    that is a whole number of milliseconds up to float rounding (the
    overwhelmingly common case for real exchange kline boundaries) converts
    exactly instead of drifting down by up to 999 microseconds."""
    return round(timestamp_seconds * 1000.0)


def resolve_candle_index_for_timestamp_ms(
    candle_timestamps_ms: Sequence[int], timestamp_ms: int
) -> int | None:
    """Exact-match only — unlike the Python renderer's nearest-candle
    crosshair lookup, a trade marker silently snapped to the wrong candle
    would misreport when an order actually filled. Returns None when no
    candle has exactly this timestamp."""
    index = bisect.bisect_left(candle_timestamps_ms, timestamp_ms)
    if (
        index < len(candle_timestamps_ms)
        and candle_timestamps_ms[index] == timestamp_ms
    ):
        return index
    return None


def build_native_ohlcv_arrays(
    candles: Sequence[OhlcCandle],
    volumes: Sequence[tuple[float, float, bool]],
) -> tuple[
    tuple[int, ...],
    tuple[float, ...],
    tuple[float, ...],
    tuple[float, ...],
    tuple[float, ...],
    tuple[float, ...],
]:
    """Merges Backtest's separately-tracked candle and volume series (both
    UTC-second-keyed) into the native ABI's single aligned-array shape.
    Strict monotonicity/positivity is left to `pack_native_ohlcv_snapshot`,
    the one source of truth for that rule."""
    if len(candles) != len(volumes):
        raise ValueError("candle and volume series must have equal length")

    timestamps_ms: list[int] = []
    opens: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    native_volumes: list[float] = []
    for (candle_ts, open_, high, low, close), (volume_ts, volume, _is_bullish) in zip(
        candles, volumes, strict=True
    ):
        if candle_ts != volume_ts:
            raise ValueError("candle and volume timestamps must be aligned")
        timestamps_ms.append(timestamp_seconds_to_ms(candle_ts))
        opens.append(open_)
        highs.append(high)
        lows.append(low)
        closes.append(close)
        native_volumes.append(volume)

    return (
        tuple(timestamps_ms),
        tuple(opens),
        tuple(highs),
        tuple(lows),
        tuple(closes),
        tuple(native_volumes),
    )


def build_native_indicator_series(
    candle_timestamps_ms: Sequence[int],
    x_data_seconds: Sequence[float],
    y_data: Sequence[float],
    *,
    rgba: int,
) -> NativeIndicatorSeries:
    """Backtest indicator samples are timestamp-keyed and often sparse (an
    EMA has no value during its warm-up window); the native ABI requires
    one finite value per candle with no gaps. Missing candles are
    forward-filled from the most recent known sample. A gap before the first
    known sample is backfilled from the first known sample, providing a stable
    pre-warmup baseline."""
    if len(x_data_seconds) != len(y_data):
        raise ValueError("indicator x_data and y_data must have equal length")

    known: dict[int, float] = {}
    for timestamp_seconds, value in zip(x_data_seconds, y_data, strict=True):
        if not math.isfinite(value):
            continue
        index = resolve_candle_index_for_timestamp_ms(
            candle_timestamps_ms, timestamp_seconds_to_ms(timestamp_seconds)
        )
        if index is not None:
            known[index] = value

    if not known:
        return NativeIndicatorSeries(
            rgba=rgba, values=(0.0,) * len(candle_timestamps_ms)
        )

    first_index = min(known.keys())
    first_known = known[first_index]

    values: list[float] = []
    last_known: float = first_known
    for candle_index in range(len(candle_timestamps_ms)):
        if candle_index in known:
            last_known = known[candle_index]
        values.append(last_known)

    return NativeIndicatorSeries(rgba=rgba, values=tuple(values))


def build_native_marker(
    marker: MarkerPoint,
    candle_timestamps_ms: Sequence[int],
) -> NativeChartMarker:
    """Converts one Python `MarkerPoint` (timestamp, price, label, hex
    color, direction string) into the native ABI's candle-index-based,
    enum-typed `NativeChartMarker`. Raises if the marker's timestamp does
    not land exactly on a real candle, or its label/direction is not one
    of the known truthful entry/exit semantics."""
    timestamp_seconds, price, label, hex_color, direction_str = marker
    index = resolve_candle_index_for_timestamp_ms(
        candle_timestamps_ms, timestamp_seconds_to_ms(timestamp_seconds)
    )
    if index is None:
        raise ValueError("marker timestamp does not align with any candle")
    kind = _MARKER_LABEL_TO_KIND.get(label)
    if kind is None:
        raise ValueError(f"marker label {label!r} has no native semantic mapping")
    direction = _MARKER_DIRECTION_STR_TO_ENUM.get(direction_str)
    if direction is None:
        raise ValueError(f"marker direction {direction_str!r} is not supported")
    return NativeChartMarker(
        candle_index=index,
        price=price,
        rgba=_hex_color_to_rgba(hex_color),
        kind=kind,
        direction=direction,
    )


def _hex_color_to_rgba(hex_color: str) -> int:
    value = hex_color.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"marker color {hex_color!r} must be a 6-digit hex string")
    return 0xFF000000 | int(value, 16)


@dataclass(slots=True)
class NativeChartSubmissionFence:
    """Rejects a submission whose caller-supplied (action_id, generation)
    token is not strictly newer than the last accepted one — guards
    against a late callback from a superseded action reaching the native
    item just because its data happens to be the same shape as the current
    one (BOT-098F6 architecture contract: "action_id/preview fencing")."""

    _last_accepted: tuple[int, int] | None = None

    def admit(self, action_id: int, generation: int) -> bool:
        token = (action_id, generation)
        if self._last_accepted is not None and token <= self._last_accepted:
            return False
        self._last_accepted = token
        return True


class NativeBacktestChartHost:
    """Owns one `QQuickWidget`-embedded `NativeChartItem` and the
    Backtest-specific conversion/fencing needed to submit real data to it.
    Construction/runtime/ABI failure raises `NativeChartRuntimeError` — a
    typed diagnostic a future factory (BOT-098F6D) can catch to fall back
    to the Python host; this class performs no fallback itself."""

    def __init__(
        self,
        widget: QQuickWidget,
        component: QQmlComponent,
        root_item: object,
        chart_item: object,
        gesture_bridge: NativeChartGestureBridge,
        timezone_bridge: NativeChartTimezoneBridge,
    ) -> None:
        # component/root_item/the bridges have no other Python-side owner
        # once create() returns — QQuickWidget.setContent() and
        # setContextProperty() do not keep them alive the way a naive
        # reading of "the widget/engine now owns this" would suggest, so
        # without holding these references here the underlying C++ objects
        # (chart_item included) get deleted out from under this host the
        # moment create()'s local variables go out of scope.
        self._widget = widget
        self._component = component
        self._root_item = root_item
        self._chart_item = chart_item
        self._gesture_bridge = gesture_bridge
        self._timezone_bridge = timezone_bridge
        self._fence = NativeChartSubmissionFence()
        self._ohlcv_revision = 0
        self._indicator_revision = 0
        self._marker_revision = 0
        self._candle_timestamps_ms: tuple[int, ...] = ()

    @classmethod
    def create(cls) -> NativeBacktestChartHost:
        widget = create_quick_widget()
        configure_native_chart_engine(widget.engine(), required=True)

        gesture_bridge = NativeChartGestureBridge()
        timezone_bridge = NativeChartTimezoneBridge()
        context = widget.engine().rootContext()
        context.setContextProperty("gestureBridge", gesture_bridge)
        context.setContextProperty("timezoneBridge", timezone_bridge)

        component = QQmlComponent(widget.engine())
        component.loadUrl(QUrl.fromLocalFile(str(_NATIVE_CHART_QML_PATH)))
        root_item = component.create()
        if component.errors() or root_item is None:
            raise NativeChartRuntimeError(
                "native Backtest chart QML did not construct: "
                + "; ".join(str(error) for error in component.errors())
            )
        widget.setContent(QUrl(), component, root_item)
        chart_item = root_item.findChild(type(root_item), "nativeChartItem")
        if chart_item is None:
            raise NativeChartRuntimeError(
                "nativeChartItem was not found after construction"
            )
        return cls(
            widget, component, root_item, chart_item, gesture_bridge, timezone_bridge
        )

    @property
    def widget(self) -> QQuickWidget:
        return self._widget

    def set_display_timezone(self, tz_name: str) -> None:
        self._root_item.setProperty("displayTimezone", tz_name)

    def set_dev_fps_enabled(self, enabled: bool) -> None:
        self._chart_item.setProperty("devFpsEnabled", bool(enabled))

    def _assert_owning_gui_thread(self) -> None:
        if QThread.currentThread() is not self._widget.thread():
            raise RuntimeError(
                "NativeBacktestChartHost must only be touched from its owning GUI "
                "thread — this call arrived from a worker thread"
            )

    def submit_ohlcv(
        self,
        candles: Sequence[OhlcCandle],
        volumes: Sequence[tuple[float, float, bool]],
        *,
        action_id: int,
        generation: int,
    ) -> bool:
        self._assert_owning_gui_thread()
        if not self._fence.admit(action_id, generation):
            return False
        timestamps, opens, highs, lows, closes, native_volumes = (
            build_native_ohlcv_arrays(candles, volumes)
        )
        self._ohlcv_revision += 1
        snapshot = pack_native_ohlcv_snapshot(
            revision=self._ohlcv_revision,
            timestamps=timestamps,
            opens=opens,
            highs=highs,
            lows=lows,
            closes=closes,
            volumes=native_volumes,
        )
        accepted = bool(self._chart_item.submitSnapshot(snapshot))
        if accepted:
            self._candle_timestamps_ms = timestamps
        return accepted

    def submit_indicators(
        self,
        series: Sequence[tuple[int, Sequence[float], Sequence[float]]],
        *,
        action_id: int,
        generation: int,
    ) -> bool:
        """`series` is `(rgba, x_data_seconds, y_data)` per indicator line."""
        self._assert_owning_gui_thread()
        if not self._fence.admit(action_id, generation):
            return False
        if not self._candle_timestamps_ms:
            return True
        native_series = tuple(
            build_native_indicator_series(
                self._candle_timestamps_ms, x_data, y_data, rgba=rgba
            )
            for rgba, x_data, y_data in series
            if x_data and y_data
        )
        self._indicator_revision += 1
        snapshot = pack_native_indicator_snapshot(
            revision=self._indicator_revision,
            candle_count=len(self._candle_timestamps_ms),
            series=native_series,
        )
        return bool(self._chart_item.submitIndicatorSnapshot(snapshot))

    def submit_markers(
        self,
        markers: Sequence[MarkerPoint],
        *,
        action_id: int,
        generation: int,
    ) -> bool:
        self._assert_owning_gui_thread()
        if not self._fence.admit(action_id, generation):
            return False
        if not self._candle_timestamps_ms:
            return True
        native_markers_list: list[NativeChartMarker] = []
        for marker in markers:
            try:
                m = build_native_marker(marker, self._candle_timestamps_ms)
                native_markers_list.append(m)
            except ValueError:
                # Out-of-window trade markers (e.g. earlier trades outside the visible/loaded kline window)
                # or unsupported labels are skipped cleanly without crashing the render pass.
                continue
        native_markers = sorted(
            native_markers_list,
            key=lambda marker: marker.candle_index,
        )
        self._marker_revision += 1
        snapshot = pack_native_marker_snapshot(
            revision=self._marker_revision,
            candle_count=len(self._candle_timestamps_ms),
            markers=native_markers,
        )
        return bool(self._chart_item.submitMarkerSnapshot(snapshot))
