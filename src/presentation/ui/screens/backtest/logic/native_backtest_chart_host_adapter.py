"""BOT-098F6D — bridges NativeBacktestChartHost (BOT-098F6B/F6C) behind the
IBacktestChartHost port so BackTestView/Presenter can drive it through the
exact same call sites as PythonBacktestChartHost, with zero awareness of
which renderer is actually behind the port.

Native scope in this slice is OHLC candles + volume + strategy-indicator
overlay lines + truthful LONG/SHORT entry/exit markers + timezone + dev FPS
(BOT-098F6 architecture contract). Anything outside that — equity/BOTH
subplot, non-candlestick chart types, script regions/info, arbitrary script
marker text — raises NativeUnsupportedFeatureError rather than silently
dropping content; BackTestView catches it and rebuilds the Python host
(BOT-098F6's "no silent visual omission" requirement).
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QWidget

from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.chart_card import (
    OhlcCandle,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.marker_layer import (
    MarkerPoint,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.native_chart_card import (
    NativeChartCard,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_adapter import (
    NativeBacktestChartHost,
)

logger = logging.getLogger("App.NativeBacktestChartHostAdapter")

#: The only set_script_markers/clear_script_markers key this slice's native
#: path understands — matches BackTestView's own _TRADE_FLAGS_KEY. Anything
#: else is a reference-script marker set, explicitly out of native scope.
_TRADE_FLAGS_KEY = "backtest_trades"
_SUPPORTED_CHART_TYPE = "candlestick"


class NativeUnsupportedFeatureError(RuntimeError):
    """Raised when the caller asked the native host for something outside
    this slice's scope (equity/BOTH subplot, non-candlestick chart type,
    script regions/info, arbitrary script markers). BackTestView must catch
    this and rebuild with the Python host — it is not a crash, it is the
    explicit "this content needs Python" signal."""


class NativeBacktestChartHostAdapter:
    """`IBacktestChartHost` implementation backed by `NativeBacktestChartHost`."""

    def __init__(self, symbol: str, native_host: NativeBacktestChartHost) -> None:
        self._symbol = symbol
        self._native_host = native_host
        self._card = NativeChartCard(symbol, native_host.widget)
        self._action_id = 1
        self._generation = 0
        self._pending_candles: list[OhlcCandle] | None = None
        # Native's indicator ABI is a full-replace snapshot (BOT-098F6B), not
        # additive, so every registered indicator's latest series is kept
        # here and the *whole* set is resubmitted on every change — mirrors
        # what ChartCard's IndicatorManager already does per-name internally.
        self._indicator_series: dict[str, tuple[int, list[float], list[float]]] = {}

    @property
    def native_host(self) -> NativeBacktestChartHost:
        """Escape hatch for tests — production code must use only the port."""
        return self._native_host

    @property
    def widget(self) -> QWidget:
        return self._card

    @property
    def symbol(self) -> str:
        return self._symbol

    def _next_generation(self) -> int:
        self._generation += 1
        return self._generation

    def add_to_header(self, widget: QWidget) -> None:
        self._card.add_to_header(widget)

    def set_dev_mode(self, enabled: bool) -> None:
        self._native_host.set_dev_fps_enabled(enabled)

    def set_display_timezone(self, tz_name: str) -> None:
        self._native_host.set_display_timezone(tz_name)

    def render_historical_data(self, data: list[OhlcCandle]) -> None:
        # BackTestView always calls render_historical_data() followed by
        # render_historical_volume() for the same render — the native ABI
        # needs both merged into one submit_ohlcv() call, so the candles are
        # held here until the matching volume call arrives.
        self._pending_candles = list(data)

    def render_historical_volume(self, data: list[tuple[float, float, bool]]) -> None:
        if self._pending_candles is None:
            raise NativeUnsupportedFeatureError(
                "render_historical_volume() called without a preceding "
                "render_historical_data() call"
            )
        candles, self._pending_candles = self._pending_candles, None
        accepted = self._native_host.submit_ohlcv(
            candles,
            data,
            action_id=self._action_id,
            generation=self._next_generation(),
        )
        if not accepted:
            raise NativeUnsupportedFeatureError("native OHLCV submission was rejected")

    def set_chart_type(self, chart_type: str) -> None:
        if chart_type != _SUPPORTED_CHART_TYPE:
            raise NativeUnsupportedFeatureError(
                f"native chart type support is candlestick-only, got {chart_type!r}"
            )

    def set_volume_visible(self, visible: bool) -> None:
        # Native always renders integrated volume (BOT-098F3); there is no
        # separate visibility toggle to wire up in this slice.
        pass

    def add_overlay_indicator(self, name: str, color: str) -> None:
        # Registers the color; update_indicator_data() supplies the series
        # and triggers the actual (whole-set) native resubmission.
        self._indicator_series[name] = (_color_to_rgba(color), [], [])

    def add_subplot_indicator(
        self, name: str, color: str, height_ratio: int = 1
    ) -> None:
        raise NativeUnsupportedFeatureError(
            "native subplot indicators (equity overlay) are not supported in this slice"
        )

    def update_indicator_data(
        self, name: str, x_data: list[float], y_data: list[float]
    ) -> None:
        if name not in self._indicator_series:
            raise NativeUnsupportedFeatureError(
                f"update_indicator_data({name!r}) called without a preceding "
                "add_overlay_indicator() call"
            )
        rgba = self._indicator_series[name][0]
        self._indicator_series[name] = (rgba, list(x_data), list(y_data))
        self._resubmit_indicators()

    def set_indicator_visible(self, name: str, visible: bool) -> None:
        # BOT-098F6D scope does not yet expose a native per-indicator
        # visibility toggle; visibility changes fall back to Python via the
        # same mechanism as any other unsupported call.
        raise NativeUnsupportedFeatureError(
            "native indicator visibility toggling is not supported in this slice"
        )

    def remove_indicator(self, name: str) -> None:
        if self._indicator_series.pop(name, None) is not None:
            self._resubmit_indicators()

    def _resubmit_indicators(self) -> None:
        series = [
            (rgba, x_data, y_data)
            for rgba, x_data, y_data in self._indicator_series.values()
        ]
        accepted = self._native_host.submit_indicators(
            series,
            action_id=self._action_id,
            generation=self._next_generation(),
        )
        if not accepted:
            raise NativeUnsupportedFeatureError(
                "native indicator submission was rejected"
            )

    def set_script_regions(
        self, key: str, spans: list[tuple[float, float, str, float]]
    ) -> None:
        raise NativeUnsupportedFeatureError("native script regions are not supported")

    def clear_script_regions(self, key: str) -> None:
        pass

    def set_script_info(self, key: str, fields: list) -> None:
        raise NativeUnsupportedFeatureError("native script info is not supported")

    def clear_script_info(self, key: str) -> None:
        pass

    def set_script_markers(self, key: str, markers: list[MarkerPoint]) -> None:
        if key != _TRADE_FLAGS_KEY:
            raise NativeUnsupportedFeatureError(
                f"native markers only support the trade-flags key, got {key!r}"
            )
        accepted = self._native_host.submit_markers(
            markers,
            action_id=self._action_id,
            generation=self._next_generation(),
        )
        if not accepted:
            raise NativeUnsupportedFeatureError("native marker submission was rejected")

    def clear_script_markers(self, key: str) -> None:
        if key != _TRADE_FLAGS_KEY:
            return
        self._native_host.submit_markers(
            [],
            action_id=self._action_id,
            generation=self._next_generation(),
        )

    def connect_timeframe_changed(self, slot) -> None:
        # The timeframe toolbar stays a QtWidgets header control per the
        # architecture contract; BackTestView wires it directly rather than
        # through the host for the native path.
        pass

    def set_active_timeframe(self, timeframe: str | None) -> None:
        pass

    def cleanup(self) -> None:
        # BackTestView.render_symbol_cards() calls widget.deleteLater() on
        # whatever it put in the layout (this.widget == self._card); the
        # native QQuickWidget is a Qt child of that card, so Qt's normal
        # parent-child teardown already disposes it. NativeBacktestChartHost
        # has no separate disposal step of its own to call (BOT-098F6B/F6C
        # never introduced one) — nothing extra to do here.
        pass


def _color_to_rgba(hex_color: str) -> int:
    value = hex_color.lstrip("#")
    if len(value) != 6:
        raise NativeUnsupportedFeatureError(
            f"indicator color {hex_color!r} must be a 6-digit hex string"
        )
    return 0xFF000000 | int(value, 16)
