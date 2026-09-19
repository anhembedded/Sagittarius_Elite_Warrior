"""The Backtest Engine screen as a contribution — `backtesting`'s own
(`EPIC-025F` PR 5.2).

Same real difference from `settings_screen()`'s shape as `dashboard_screen.py`
(same pull request, read its docstring for the full reasoning): which
concrete View this install uses is a named choice read from `IConfig`
(`EPIC-013F`), so the view factory needs `container` at construction time,
and `PresenterManager.navigate_to()` calls `view_factory()` with zero
arguments. `BacktestingModule.boot()` stashes `context.container` for this
call.

Both factories below check the concrete type they get, the same real check
`dashboard_screen()`/`settings_screen()`/`welcome_screen()` all make and the
legacy `BacktestScreenModule.create_view()`/`create_presenter()` this
replaces never did: `build_backtest_view()` returns `IBacktestView` (a
`Protocol`, unrelated to `BaseView` by inheritance) and `BackTestPresenter`
needs `BackTestView` specifically, not the generic `BaseView` every
`ScreenContribution` factory is typed over. The legacy module's own
`create_view()`/`create_presenter()` carried the identical mismatch, silent
only because `module.py` sat in `pyproject.toml`'s per-file `mypy` exclude
list; this file is not excluded, so the check that was always missing here
now runs for real.
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
    from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view import (
        BackTestView,
    )

    if not isinstance(view, BackTestView):
        raise TypeError(
            f"the Backtest screen's presenter was handed a {type(view).__name__}, "
            "not a BackTestView"
        )
    return BackTestPresenter(view, container)


def backtest_screen(container: IContainer) -> ScreenContribution:
    """`backtesting`'s Backtest Engine screen. Takes `container` for the
    reason this module's own docstring explains."""

    def _build_backtest_view() -> BaseView:
        # `build_backtest_view`, not `BackTestView()` (`EPIC-013F`): a View
        # is never swapped while the app runs, so the config-driven choice
        # is read once, here.
        from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view import (
            BackTestView,
        )
        from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.view_factory import (
            build_backtest_view,
        )

        config = container.resolve(IConfig)
        view = build_backtest_view(config)
        if not isinstance(view, BackTestView):
            raise TypeError(
                f"build_backtest_view() returned a {type(view).__name__}, "
                "not a BackTestView"
            )
        return view

    return ScreenContribution(
        contributor_id="backtesting",
        route=BACKTEST_ROUTE,
        view_factory=_build_backtest_view,
        presenter_factory=_build_backtest_presenter,
        nav=_NAV,
    )
