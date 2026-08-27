"""Declared contracts of the Backtest screen — interfaces only, no implementation.

@details A directory of its own because `architecture-rule.md` §5.2 forbids
an interface and its implementation sharing a `dir`: a port here is one
abstraction level above `../backtest_view.py`, `../coordinators/` and
`../logic/`.

A port may import the **types its contract speaks in** (enums, ViewModels,
other ports); it must not import the concrete widget, host or coordinator
that implements it — that dependency runs the other way. Two members of
`IBacktestView` needed a port of their own for exactly that reason:
`chart_controls` and `set_chart_host_factory()` would otherwise have been
typed `object`, which is the implicit contract `EPIC-012` exists to remove
wearing a type annotation.

Precedent for the layout: `presentation/ui/state/ports/`.
"""

from .i_backtest_chart_controls import IBacktestChartControls
from .i_backtest_chart_host import IBacktestChartHost
from .i_backtest_chart_host_factory import IBacktestChartHostFactory
from .i_backtest_view import IBacktestView

__all__ = [
    "IBacktestChartControls",
    "IBacktestChartHost",
    "IBacktestChartHostFactory",
    "IBacktestView",
]
