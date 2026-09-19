"""The Backtest Engine screen as a contribution — `backtesting`'s own
(`EPIC-025F` PR 5.2).

Same real difference from `settings_screen()`'s shape as `dashboard_screen.py`
(same pull request, read its docstring for the full reasoning): which
concrete View this install uses is a named choice read from `IConfig`
(`EPIC-013F`), so the view factory needs `container` at construction time,
and `PresenterManager.navigate_to()` calls `view_factory()` with zero
arguments. `BacktestingModule.register()` stashes `context.container` for
this call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import NavMetadata
from Sagittarius_Elite_Warrior.src.core.contracts.screen_contribution import (
    ScreenContribution,
)
from sagittarius_engine.interfaces.i_config import IConfig

if TYPE_CHECKING:
    from sagittarius_engine.extensions.pyside_mvc import BasePresenter, BaseView
    from sagittarius_engine.interfaces.i_container import IContainer

BACKTEST_ROUTE = "backtest"

_NAV = NavMetadata(
    title="Backtest Engine",
    icon="bar-chart-2",
    section_key="QUANT ENGINE",
    section_sequence=20,
    item_sequence=10,
)


def _build_backtest_presenter(view: BaseView, container: IContainer) -> BasePresenter:
    from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_presenter import (
        BackTestPresenter,
    )

    return BackTestPresenter(view, container)


def backtest_screen(container: IContainer) -> ScreenContribution:
    """`backtesting`'s Backtest Engine screen. Takes `container` for the
    reason this module's own docstring explains."""

    def _build_backtest_view() -> BaseView:
        # `build_backtest_view`, not `BackTestView()` (`EPIC-013F`): a View
        # is never swapped while the app runs, so the config-driven choice
        # is read once, here.
        from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.view_factory import (
            build_backtest_view,
        )

        config = container.resolve(IConfig)
        return build_backtest_view(config)

    return ScreenContribution(
        contributor_id="backtesting",
        route=BACKTEST_ROUTE,
        view_factory=_build_backtest_view,
        presenter_factory=_build_backtest_presenter,
        nav=_NAV,
    )
