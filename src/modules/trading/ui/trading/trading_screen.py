"""The Trading screen as a contribution — `trading`'s own (`EPIC-025F` PR 5.2).

Same shape `settings_screen()` established (`EPIC-025E` PR 4.4e). See
`dashboard_screen.py` (same module, same pull request) for why Dashboard
needed `TradingModule`'s stashed container and this screen does not:
`TradingView()` takes no constructor arguments at all.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import NavMetadata
from Sagittarius_Elite_Warrior.src.core.contracts.screen_contribution import (
    ScreenContribution,
)

if TYPE_CHECKING:
    from sagittarius_engine.extensions.pyside_mvc import BasePresenter, BaseView
    from sagittarius_engine.interfaces.i_container import IContainer

TRADING_ROUTE = "trading"

#: Between Dashboard (10) and Data Management (20) — unchanged from
#: `TradingScreenModule`'s own placement.
_NAV = NavMetadata(
    title="Trading",
    icon="chart-candlestick",
    section_sequence=10,
    item_sequence=15,
)


def _build_trading_view() -> BaseView:
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.trading.trading_view import (
        TradingView,
    )

    return TradingView()


def _build_trading_presenter(view: BaseView, container: IContainer) -> BasePresenter:
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.trading.trading_presenter import (
        TradingPresenter,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.trading.trading_view import (
        TradingView,
    )

    if not isinstance(view, TradingView):
        raise TypeError(
            f"the Trading screen's presenter was handed a {type(view).__name__}, "
            "not a TradingView"
        )
    return TradingPresenter(view, container)


def trading_screen() -> ScreenContribution:
    """`trading`'s Trading screen, described the way `settings_screen()`
    describes the shell's own screen."""
    return ScreenContribution(
        contributor_id="trading",
        route=TRADING_ROUTE,
        view_factory=_build_trading_view,
        presenter_factory=_build_trading_presenter,
        nav=_NAV,
    )
