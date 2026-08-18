from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Protocol

from PySide6.QtWidgets import QWidget

from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
    ChartCard,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.chart_card import (
    OhlcCandle,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_runtime import (
    NativeChartRuntimeError,
)

logger = logging.getLogger("App.BacktestChartHostFactory")

#: One-off env override, following the same os.environ.get(...) convention
#: native_chart_runtime.py already uses for SAGITTARIUS_NATIVE_QML_IMPORT_PATH
#: — this codebase has no ConfigManager env layer wired into the real app.
_BACKEND_ENV_OVERRIDE = "SAGITTARIUS_BACKTEST_CHART_BACKEND"
_PYTHON_BACKEND = "python"
_NATIVE_BACKEND = "native"
_AUTO_BACKEND = "auto"


class IBacktestChartHost(Protocol):
    """
    @brief Backtest-only chart host port (BOT-098F6A).

    @details The narrow set of chart operations BackTestView/Presenter
    actually use — nothing more. This is the seam that lets a future native
    host (BOT-098F6B) sit behind the exact same call sites without the View
    or Presenter ever importing a concrete renderer. A host wraps a widget;
    it is not itself the widget, since a native host will own a
    `QQuickWidget` rather than being one.
    """

    @property
    def widget(self) -> QWidget:
        """The widget BackTestView inserts into its chart layout."""
        ...

    @property
    def symbol(self) -> str: ...

    def add_to_header(self, widget: QWidget) -> None: ...

    def set_dev_mode(self, enabled: bool) -> None: ...

    def set_display_timezone(self, tz_name: str) -> None: ...

    def render_historical_data(self, data: list[OhlcCandle]) -> None: ...

    def render_historical_volume(
        self, data: list[tuple[float, float, bool]]
    ) -> None: ...

    def set_chart_type(self, chart_type: str) -> None: ...

    def set_volume_visible(self, visible: bool) -> None: ...

    def add_overlay_indicator(self, name: str, color: str) -> None: ...

    def add_subplot_indicator(
        self, name: str, color: str, height_ratio: int = 1
    ) -> None: ...

    def update_indicator_data(
        self, name: str, x_data: list[float], y_data: list[float]
    ) -> None: ...

    def set_indicator_visible(self, name: str, visible: bool) -> None: ...

    def remove_indicator(self, name: str) -> None: ...

    def set_script_regions(
        self, key: str, spans: list[tuple[float, float, str, float]]
    ) -> None: ...

    def clear_script_regions(self, key: str) -> None: ...

    def set_script_info(self, key: str, fields: list) -> None: ...

    def clear_script_info(self, key: str) -> None: ...

    def set_script_markers(self, key: str, markers: list) -> None: ...

    def clear_script_markers(self, key: str) -> None: ...

    def connect_timeframe_changed(self, slot: Callable[[str], None]) -> None:
        """Wire a callback to the chart header's timeframe toolbar clicks."""
        ...

    def set_active_timeframe(self, timeframe: str | None) -> None:
        """Mirror the ViewModel's selected timeframe onto the chart header."""
        ...

    def cleanup(self) -> None: ...


class PythonBacktestChartHost:
    """
    @brief Python `ChartCard`/`pyqtgraph` implementation of `IBacktestChartHost`.

    @details Pure delegation — wraps one `ChartCard` instance without
    rewriting any of its internals, so existing rendering, LOD, cached
    interaction and crosshair behavior are exactly unchanged. `chart_card` is
    an explicit escape hatch for tests that need `ChartCard`-internal state
    (fps overlay, plot layout, toolbar buttons, ...); production code must
    never use it — reach only the port methods above.
    """

    def __init__(self, chart_card: ChartCard) -> None:
        self._chart_card = chart_card

    @property
    def chart_card(self) -> ChartCard:
        return self._chart_card

    @property
    def widget(self) -> QWidget:
        return self._chart_card

    @property
    def symbol(self) -> str:
        return self._chart_card.symbol

    def add_to_header(self, widget: QWidget) -> None:
        self._chart_card.add_to_header(widget)

    def set_dev_mode(self, enabled: bool) -> None:
        self._chart_card.set_dev_mode(enabled)

    def set_display_timezone(self, tz_name: str) -> None:
        self._chart_card.set_display_timezone(tz_name)

    def render_historical_data(self, data: list[OhlcCandle]) -> None:
        self._chart_card.render_historical_data(data)

    def render_historical_volume(self, data: list[tuple[float, float, bool]]) -> None:
        self._chart_card.render_historical_volume(data)

    def set_chart_type(self, chart_type: str) -> None:
        self._chart_card.set_chart_type(chart_type)

    def set_volume_visible(self, visible: bool) -> None:
        self._chart_card.set_volume_visible(visible)

    def add_overlay_indicator(self, name: str, color: str) -> None:
        self._chart_card.add_overlay_indicator(name, color)

    def add_subplot_indicator(
        self, name: str, color: str, height_ratio: int = 1
    ) -> None:
        self._chart_card.add_subplot_indicator(name, color, height_ratio)

    def update_indicator_data(
        self, name: str, x_data: list[float], y_data: list[float]
    ) -> None:
        self._chart_card.update_indicator_data(name, x_data, y_data)

    def set_indicator_visible(self, name: str, visible: bool) -> None:
        self._chart_card.set_indicator_visible(name, visible)

    def remove_indicator(self, name: str) -> None:
        self._chart_card.remove_indicator(name)

    def set_script_regions(
        self, key: str, spans: list[tuple[float, float, str, float]]
    ) -> None:
        self._chart_card.set_script_regions(key, spans)

    def clear_script_regions(self, key: str) -> None:
        self._chart_card.clear_script_regions(key)

    def set_script_info(self, key: str, fields: list) -> None:
        self._chart_card.set_script_info(key, fields)

    def clear_script_info(self, key: str) -> None:
        self._chart_card.clear_script_info(key)

    def set_script_markers(self, key: str, markers: list) -> None:
        self._chart_card.set_script_markers(key, markers)

    def clear_script_markers(self, key: str) -> None:
        self._chart_card.clear_script_markers(key)

    def connect_timeframe_changed(self, slot: Callable[[str], None]) -> None:
        self._chart_card.toolbar.sig_timeframe_changed.connect(slot)

    def set_active_timeframe(self, timeframe: str | None) -> None:
        self._chart_card.toolbar.set_active(timeframe)

    def cleanup(self) -> None:
        self._chart_card.cleanup()


class BacktestChartHostFactory:
    """
    @brief Transient, view-owned factory for `IBacktestChartHost` instances.

    @details Every `BackTestView.render_symbol_cards()` call asks for a fresh
    host per symbol; nothing here is cached or shared across views — no
    QWidget/QQuickWidget this factory produces is ever a singleton. Only this
    factory, `PythonBacktestChartHost` and `NativeBacktestChartHostAdapter`
    are allowed to import a concrete renderer directly — `BackTestView`/
    `BackTestPresenter` reach it only through `IBacktestChartHost`
    (BOT-098F6A acceptance criteria #2).

    `backend` resolves in this order: the `SAGITTARIUS_BACKTEST_CHART_BACKEND`
    env var, then the caller-supplied value (from
    `backtest.chart.backend` config, resolved by `BackTestPresenter`), then
    `"python"`. `"native"`/`"auto"` both attempt native first; a missing
    plugin, ABI mismatch or QML construction failure — the exact failure
    modes `NativeChartRuntimeError` already covers — logs one actionable
    warning and falls back to Python rather than ever leaving a blank chart.
    `"auto"` exists as a distinct value only for forward config compatibility
    with `"native"` (no different runtime behavior in this slice yet).
    """

    def create(
        self,
        symbol: str,
        *,
        use_opengl: bool = False,
        cached_interaction: bool = False,
        backend: str = _PYTHON_BACKEND,
    ) -> IBacktestChartHost:
        resolved_backend = os.environ.get(_BACKEND_ENV_OVERRIDE, backend)
        if resolved_backend in (_NATIVE_BACKEND, _AUTO_BACKEND):
            native_host = self._try_create_native(symbol)
            if native_host is not None:
                return native_host
        return self._create_python(
            symbol, use_opengl=use_opengl, cached_interaction=cached_interaction
        )

    def _create_python(
        self, symbol: str, *, use_opengl: bool, cached_interaction: bool
    ) -> PythonBacktestChartHost:
        chart_card = ChartCard(
            symbol,
            use_opengl=use_opengl,
            cached_interaction=cached_interaction,
        )
        return PythonBacktestChartHost(chart_card)

    def _try_create_native(self, symbol: str):
        # Imported lazily so the Python-only path never needs the native
        # module importable at all, matching how every other native-chart
        # entry point in this codebase treats the plugin as optional.
        from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_adapter import (
            NativeBacktestChartHost,
        )
        from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_host_adapter import (
            NativeBacktestChartHostAdapter,
        )

        try:
            native_host = NativeBacktestChartHost.create()
        except NativeChartRuntimeError as error:
            logger.warning(
                "Native Backtest chart unavailable, falling back to Python: %s",
                error,
            )
            return None
        return NativeBacktestChartHostAdapter(symbol, native_host)
