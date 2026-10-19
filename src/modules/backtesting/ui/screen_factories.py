"""The two factories behind the Backtest screen's `Deferred` targets (`BOT-148`).

`backtest_screen.py` names these by import path so that `contribute()` imports no widget
module; this file is what is imported when the route is first opened. They keep the
concrete-type checks the screen has always made: `build_backtest_view()` returns
`IBacktestView` (a `Protocol`, unrelated to `BaseView` by inheritance) and
`BackTestPresenter` needs a `BackTestView`, not the generic `BaseView` every
`ScreenContribution` factory is typed over.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sagittarius_engine.interfaces.i_config import IConfig

from .backtest_presenter import BackTestPresenter
from .backtest_view import BackTestView
from .view_factory import build_backtest_view

if TYPE_CHECKING:
    from sagittarius_engine.extensions.pyside_mvc import BaseView
    from sagittarius_engine.interfaces.i_container import IContainer


def build_backtest_screen_view(container: IContainer) -> BackTestView:
    """The View this install is configured for, chosen once here (`EPIC-013F`): a View is never
    swapped while the app runs, so the config-driven choice is read at construction."""
    view = build_backtest_view(container.resolve(IConfig))
    if not isinstance(view, BackTestView):
        raise TypeError(
            f"build_backtest_view() returned a {type(view).__name__}, "
            "not a BackTestView"
        )
    return view


def build_backtest_screen_presenter(
    view: BaseView, container: IContainer
) -> BackTestPresenter:
    if not isinstance(view, BackTestView):
        raise TypeError(
            f"the Backtest screen's presenter was handed a {type(view).__name__}, "
            "not a BackTestView"
        )
    return BackTestPresenter(view, container)
