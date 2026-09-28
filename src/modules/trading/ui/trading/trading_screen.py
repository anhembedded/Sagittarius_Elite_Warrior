"""The Trading screen as a contribution — `trading`'s own (`EPIC-025F` PR 5.2).

Same shape `settings_screen()` established (`EPIC-025E` PR 4.4e). Until
`EPIC-027O`, `TradingView()` took no constructor arguments at all, unlike
`dashboard_screen.py`'s own `DashboardView` — that difference is gone now:
`TradingView` needs `market_type` at construction too (which Positions/
Holdings panel to place, whether to hide the leverage row), so this screen
takes `container` the same way `dashboard_screen(container)` already does,
for the identical reason.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import NavMetadata
from Sagittarius_Elite_Warrior.src.core.contracts.screen_contribution import (
    ScreenContribution,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
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


def trading_screen(container: IContainer) -> ScreenContribution:
    """`trading`'s Trading screen, described the way `settings_screen()`
    describes the shell's own screen.

    `container` — new since `EPIC-027O`, same reason `dashboard_screen`
    already takes it: `PresenterManager.navigate_to()` calls `view_factory()`
    with zero arguments (a hard Engine constraint, `dashboard_screen.py`'s
    own docstring), so it has to be closed over here, at the point this
    `ScreenContribution` itself is built.
    """

    def _build_trading_view() -> BaseView:
        from Sagittarius_Elite_Warrior.src.modules.trading.ui.trading.trading_view import (
            TradingView,
        )

        return TradingView(market_type=container.resolve(TradingVenue).market_type)

    return ScreenContribution(
        contributor_id="trading",
        route=TRADING_ROUTE,
        view_factory=_build_trading_view,
        presenter_factory=_build_trading_presenter,
        nav=_NAV,
    )
