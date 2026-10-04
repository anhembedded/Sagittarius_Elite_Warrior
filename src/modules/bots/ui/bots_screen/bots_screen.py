"""The Bots screen as a contribution (`EPIC-029F`, ADR D19): NAVIGATION item
18, between the Spot desk (17) and the Database (20).

Lazy, as every `ScreenContribution` must be: the factories are `Deferred`
import paths, so nothing below imports Qt until the route is first opened and
a headless run never pays for it. The shell builds the view and the presenter
from the same contribution, so the presenter always receives this `BotsView`.
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

BOTS_ROUTE = "bots"

_NAV = NavMetadata(
    title="Bots",
    icon="bot",
    section_sequence=10,
    item_sequence=18,
)

_PACKAGE = "Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen"
_VIEW: Deferred[BaseView] = Deferred(f"{_PACKAGE}.bots_view:BotsView")
_PRESENTER: Deferred[BasePresenter] = Deferred(
    f"{_PACKAGE}.bots_presenter:BotsPresenter"
)


def bots_screen() -> ScreenContribution:
    return ScreenContribution(
        contributor_id="bots",
        route=BOTS_ROUTE,
        view_factory=_VIEW,
        presenter_factory=_PRESENTER,
        nav=_NAV,
    )
