"""What `TradingPresenter` needs of the Trading screen's View — stated,
not implied.

@details `EPIC-021I`. Same reasoning as `IBacktestView`
(`architecture-rule.md` §2.1): an implicit, duck-typed boundary lets the
declared contract and the real one drift apart with nothing to notice —
exactly what happened to the engine's own `IView` (declares `bind()`,
implemented by nobody). `Protocol`, not an ABC, for reason (a): the only
implementer (`TradingView`) is a `QWidget` subclass via `BaseView`, where
`ABCMeta` collides with Shiboken's metaclass.

Deliberately small: this screen's chart is single-symbol (unlike Dev
Board's per-symbol `active_charts` dict), and every other piece of state
(current symbol, toggle busy/enabled, status text, session stats) lives on
`TradingViewModel`, which is not a View member — the View is handed it
once via `set_view_model()` and binds its own widgets to its signals, the
same split `SettingsView`/`SettingsViewModel` uses.

**Enforcement:** `presentation/` is excluded from the `mypy` gate wholesale
(`pyproject.toml`, `EPIC-002A`), so `tests/unit/presentation/ui/screens/
trading/test_trading_view_contract.py` — an `ast` walk over the
Presenter-side modules — is the mechanism that keeps this contract honest,
not a type checker.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...components.chart_card import ChartCard
from ...qml.OpenOrdersTable.open_order_row import OpenOrderRow
from ...qml.PositionsTable.positions_row import PositionRow
from .trading_view_model import TradingViewModel

#: `set_view_model`'s second argument — kept for the same reason
#: `IBacktestView` keeps it: `BaseView.set_view_model` still accepts it.
DEFAULT_VIEW_MODEL_CONTEXT_NAME = "viewModel"


@runtime_checkable
class ITradingView(Protocol):
    """@brief The Trading screen's Presenter<->View contract — 4 members."""

    #: The single live chart this screen shows. `TradingPresenter` renders
    #: historical candles and live ticks onto it directly, on the main
    #: thread, from its own Qt-signal-marshaled slots
    #: (`chart.render_historical_data(...)`, `chart.append_closed_candle(...)`,
    #: ...) — those `ChartCard` methods are not themselves part of this
    #: port, only the attribute that reaches them. `ChartCoordinator`
    #: (the background worker) never touches `view` at all.
    chart: ChartCard

    def set_view_model(
        self,
        view_model: TradingViewModel,
        context_name: str = DEFAULT_VIEW_MODEL_CONTEXT_NAME,
    ) -> None:
        """Registers the ViewModel and builds every child that needs it."""
        ...

    def set_positions(self, rows: list[PositionRow]) -> None:
        """Replaces the Positions table's rows entirely. The View's own
        `PositionsPanel` does the QML-facing-dict projection
        (`positions_row.position_row_to_qml`) — this port stays in terms
        of the plain domain-shaped row, not that rendering detail."""
        ...

    def set_open_orders(self, rows: list[OpenOrderRow]) -> None:
        """Replaces the Open Orders table's rows entirely — see
        `set_positions`."""
        ...
