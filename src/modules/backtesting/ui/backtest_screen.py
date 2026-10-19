"""The Backtest Engine screen as a contribution — `backtesting`'s own
(`EPIC-025F` PR 5.2).

Same real difference from the plain `ScreenContribution` shape as the Dev Board's
`dashboard_screen.py` had (same pull request; `EPIC-033P` deleted it): which
concrete View this install uses is a named choice read from `IConfig`
(`EPIC-013F`), so the view factory needs `container` at construction time,
and `PresenterManager.navigate_to()` calls `view_factory()` with zero
arguments. `BacktestingModule.boot()` stashes `context.container` for this
call.

Both factories are `Deferred` import paths into `screen_factories.py` (`BOT-148`), so nothing
here imports Qt until the route is first opened; that file keeps the concrete-type check each
makes: `build_backtest_view()` returns `IBacktestView` (a `Protocol`, unrelated to `BaseView`
by inheritance) and `BackTestPresenter` needs `BackTestView` specifically, not the generic
`BaseView` every `ScreenContribution` factory is typed over.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.deferred import Deferred
from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import NavMetadata
from Sagittarius_Elite_Warrior.src.core.contracts.screen_contribution import (
    ScreenContribution,
)

if TYPE_CHECKING:
    from sagittarius_engine.extensions.pyside_mvc import BasePresenter, BaseView
    from sagittarius_engine.interfaces.i_container import IContainer

BACKTEST_ROUTE = "backtest"

_NAV = NavMetadata(
    title="Backtest engine",
    icon="bar-chart-2",
    section_key="QUANT ENGINE",
    section_sequence=20,
    item_sequence=10,
)


_PACKAGE = "Sagittarius_Elite_Warrior.src.modules.backtesting.ui"
_VIEW: Deferred[BaseView] = Deferred(
    f"{_PACKAGE}.screen_factories:build_backtest_screen_view"
)
_PRESENTER: Deferred[BasePresenter] = Deferred(
    f"{_PACKAGE}.screen_factories:build_backtest_screen_presenter"
)


def backtest_screen(container: IContainer) -> ScreenContribution:
    """`backtesting`'s Backtest Engine screen. Takes `container` for the
    reason this module's own docstring explains."""

    return ScreenContribution(
        contributor_id="backtesting",
        route=BACKTEST_ROUTE,
        view_factory=_VIEW.bind(container),
        presenter_factory=_PRESENTER,
        nav=_NAV,
    )
