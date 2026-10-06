"""The Trade mode as a contribution (`EPIC-033I`): one mode for every venue.

HLD §11.2.1: trading one venue by hand and seeing its account is one job, so
Futures and Spot are one mode with a venue choice, not two screens. It is
the default mode: the first run opens here; later runs open on the mode the
last one ended in (`EPIC-033C`).

Lazy, as every `ScreenContribution` must be: the factories are `Deferred`
import paths, so nothing below imports Qt until the mode is built.
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

TRADE_ROUTE = "trade"
_NAV = NavMetadata(
    title="Trade",
    # Not Market's candlestick: two modes with one icon on the mode bar
    # tell the person nothing.
    icon="dollar-sign",
    section_sequence=10,
    item_sequence=16,
)
_PACKAGE = "Sagittarius_Elite_Warrior.src.modules.trading.ui.trade"
_VIEW: Deferred[BaseView] = Deferred(f"{_PACKAGE}.trade_view:TradeView")
_PRESENTER: Deferred[BasePresenter] = Deferred(
    f"{_PACKAGE}.trade_presenter:build_trade_presenter"
)


def trade_screen() -> ScreenContribution:
    return ScreenContribution(
        contributor_id="trading",
        route=TRADE_ROUTE,
        view_factory=_VIEW,
        presenter_factory=_PRESENTER,
        nav=_NAV,
        is_default=True,
    )
