"""`ChartCard`-backed implementations of the Backtest chart-host port.

@details The port itself lives in `../ports/i_backtest_chart_host.py`
(`EPIC-012B`) — this module is one abstraction level below it and holds
only concrete things: the `pyqtgraph` host and the factory that builds it.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
    ChartCard,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.chart_card import (
    OhlcCandle,
)

from ..ports.i_backtest_chart_host import IBacktestChartHost

logger = logging.getLogger("App.BacktestChartHostFactory")


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

    def add_overlay_indicator(self, name: str, color: str, width: int = 2) -> None:
        self._chart_card.add_overlay_indicator(name, color, width)

    def add_subplot_indicator(
        self,
        name: str,
        color: str,
        height_ratio: int = 1,
        group: str | None = None,
    ) -> None:
        self._chart_card.add_subplot_indicator(name, color, height_ratio, group=group)

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
    QWidget this factory produces is ever a singleton. Only this factory and
    `PythonBacktestChartHost` are allowed to import a concrete renderer
    directly — `BackTestView`/`BackTestPresenter` reach it only through
    `IBacktestChartHost` (BOT-098F6A acceptance criteria #2).
    """

    def create(
        self,
        symbol: str,
        *,
        use_opengl: bool = False,
        cached_interaction: bool = False,
    ) -> IBacktestChartHost:
        logger.info("Backtest chart host initialized for symbol '%s'.", symbol)
        chart_card = ChartCard(
            symbol,
            use_opengl=use_opengl,
            cached_interaction=cached_interaction,
        )
        return PythonBacktestChartHost(chart_card)
