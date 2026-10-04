"""The Bots screen as a contribution (`EPIC-029F`, ADR D19): NAVIGATION item
18, between the Spot desk (17) and the Database (20).

Lazy, as every `ScreenContribution` here: nothing below imports Qt until the
route is first opened, so a headless run never pays for it.
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

BOTS_ROUTE = "bots"

_NAV = NavMetadata(
    title="Bots",
    icon="bot",
    section_sequence=10,
    item_sequence=18,
)


def _build_bots_view() -> BaseView:
    from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
        BotsView,
    )

    return BotsView()


def _build_bots_presenter(view: BaseView, container: IContainer) -> BasePresenter:
    from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_presenter import (
        BotsPresenter,
    )
    from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
        BotsView,
    )

    if not isinstance(view, BotsView):
        raise TypeError(
            f"the Bots screen's presenter was handed a {type(view).__name__}, "
            "not a BotsView"
        )
    return BotsPresenter(view, container)


def bots_screen() -> ScreenContribution:
    return ScreenContribution(
        contributor_id="bots",
        route=BOTS_ROUTE,
        view_factory=_build_bots_view,
        presenter_factory=_build_bots_presenter,
        nav=_NAV,
    )
