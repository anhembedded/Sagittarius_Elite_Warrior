"""How the Backtest screen asks for a chart host.

@details `EPIC-013B`. `BackTestPresenter` hands the View a DI-resolved
factory through `IBacktestView.set_chart_host_factory()`; without this port
that parameter had no type at all, so nothing said what the View was
allowed to do with the object it received.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .i_backtest_chart_host import IBacktestChartHost


@runtime_checkable
class IBacktestChartHostFactory(Protocol):
    """
    @brief Builds one chart host per symbol. Nothing it returns is shared.

    @details **`Protocol`, not an ABC**, under `architecture-rule.md` §2.1
    reason **(b)**: `BackTestView` constructs a default implementation for
    itself, and the concrete factory is free to carry whatever base it
    needs — requiring inheritance here would buy nothing the structural
    check does not already give.
    """

    def create(
        self,
        symbol: str,
        *,
        use_opengl: bool = False,
        cached_interaction: bool = False,
    ) -> IBacktestChartHost:
        """Returns a fresh host for `symbol`. Never cached, never a singleton."""
        ...
