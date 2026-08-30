"""`DataManagementKlineInspectorSource` — translates `DataManagementViewModel`'s
real symbol/interval/candle-list state into the plain `get_*` callables
`KlineInspectorVM` wants.

Kept apart from `kline_inspector_dialog.py` (the `QmlOverlay` composition
root that constructs this and wires it in) per `architecture-rule.md` §5: a
translation adapter and the widget wiring that constructs it are different
abstraction levels and do not share a file — the same split
`backtest_time_range_source.py`/`time_range_picker_dialog.py` already use.

`KlineInspectorVM` takes three plain callables directly, not an `ISource`
ABC (its own docstring: callback-constructed the same way `SelectListVM`/
`TradeLogVM` are) — so this adapter implements no interface, it just has
three methods that get passed bound.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData

    from ..data_management_view_model import DataManagementViewModel


class DataManagementKlineInspectorSource:
    """Reads Data Management's currently-inspected symbol/interval/candles.

    Read-only, unlike `BacktestSymbolPickerSource`: `KlineInspectorVM` is a
    display table, not a picker (`KlineInspectorTable/NOTES.md` — no
    choose-and-close), so this adapter has no `set_*`/write method at all.
    """

    def __init__(self, view_model: DataManagementViewModel) -> None:
        self._view_model = view_model

    def get_klines(self) -> Sequence[MarketData]:
        return self._view_model.kline_inspector_klines

    def get_symbol(self) -> str:
        return self._view_model.klineInspectorSymbol

    def get_interval(self) -> str:
        return self._view_model.klineInspectorInterval
