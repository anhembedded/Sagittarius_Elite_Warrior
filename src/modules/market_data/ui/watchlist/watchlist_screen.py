"""The Watchlist screen as a contribution (`BOT-019`) — same shape
`database_screen()` already established for this module's other screen.
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

WATCHLIST_ROUTE = "watchlist"

_NAV = NavMetadata(
    title="Watchlist",
    icon="eye",
    section_sequence=10,
    item_sequence=30,
)


def _build_watchlist_view() -> BaseView:
    """Builds the view, importing it only now — the same lazy shape every
    `ScreenContribution` factory in this codebase uses, so a headless
    `sync` run never imports Qt to answer a question it never asks."""
    from Sagittarius_Elite_Warrior.src.modules.market_data.ui.watchlist.watchlist_view import (
        WatchlistView,
    )

    return WatchlistView()


def _build_watchlist_presenter(view: BaseView, container: IContainer) -> BasePresenter:
    from Sagittarius_Elite_Warrior.src.modules.market_data.ui.watchlist.watchlist_presenter import (
        WatchlistPresenter,
    )
    from Sagittarius_Elite_Warrior.src.modules.market_data.ui.watchlist.watchlist_view import (
        WatchlistView,
    )

    if not isinstance(view, WatchlistView):
        raise TypeError(
            f"the Watchlist screen's presenter was handed a {type(view).__name__}, "
            "not a WatchlistView"
        )
    return WatchlistPresenter(view, container)


def watchlist_screen() -> ScreenContribution:
    """`market_data`'s Watchlist screen, described the way
    `database_screen()` describes this module's other screen."""
    return ScreenContribution(
        contributor_id="market_data",
        route=WATCHLIST_ROUTE,
        view_factory=_build_watchlist_view,
        presenter_factory=_build_watchlist_presenter,
        nav=_NAV,
    )
