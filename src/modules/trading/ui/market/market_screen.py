"""The Market mode as a contribution (`EPIC-033H`): Ctrl+1, the first mode.

HLD §11.2.1 puts watching the market first on the mode bar, so its item
sequence sits before every other mode's. Lazy, as every
`ScreenContribution` must be: the factories are `Deferred` import paths, so
nothing below imports Qt until the mode is built.
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

MARKET_ROUTE = "market"
_NAV = NavMetadata(
    title="Market",
    icon="chart-candlestick",
    section_sequence=10,
    item_sequence=5,
)
_PACKAGE = "Sagittarius_Elite_Warrior.src.modules.trading.ui.market"
_VIEW: Deferred[BaseView] = Deferred(f"{_PACKAGE}.market_view:MarketView")
_PRESENTER: Deferred[BasePresenter] = Deferred(
    f"{_PACKAGE}.market_presenter:build_market_presenter"
)


def market_screen() -> ScreenContribution:
    return ScreenContribution(
        contributor_id="trading",
        route=MARKET_ROUTE,
        view_factory=_VIEW,
        presenter_factory=_PRESENTER,
        nav=_NAV,
    )
