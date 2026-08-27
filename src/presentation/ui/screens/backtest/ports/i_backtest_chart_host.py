"""The chart-host contract the Backtest screen programs against.

@details Moved out of `../logic/backtest_chart_host.py` by `EPIC-012B`:
that file held the port, its `ChartCard` implementation and the factory in
one 224-line module, which is exactly the interface-beside-implementation
shape `architecture-rule.md` §5.1 forbids. Only the port moved — behaviour
is unchanged.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.chart_card import (
    OhlcCandle,
)


@runtime_checkable
class IBacktestChartHost(Protocol):
    """
    @brief Backtest-only chart host port (BOT-098F6A).

    @details The narrow set of chart operations BackTestView/Presenter
    actually use — nothing more.

    `Protocol` rather than an ABC under `architecture-rule.md` §2.1 reason
    **(a)**: the sole implementation wraps a `ChartCard`, a `QObject`
    subclass, and `ABCMeta` collides with Shiboken's metaclass — the same
    constraint `ui/kit/style.py` documents as the reason `apply_role()` is
    composition rather than a mixin.

    `PythonBacktestChartHost` (pyqtgraph) is
    the sole implementation — a native C++/QML host existed behind this
    same port until it was deleted outright (never rendered a production
    frame in ~5 months live; see the epic that removed it), confirming the
    port itself was worth keeping even though only one host ever used it
    for real.
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

    def add_overlay_indicator(self, name: str, color: str, width: int = 2) -> None: ...

    def add_subplot_indicator(
        self,
        name: str,
        color: str,
        height_ratio: int = 1,
        group: str | None = None,
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
