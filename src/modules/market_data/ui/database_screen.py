"""The Database (Data Management) screen as a contribution — `market_data`'s
own (`EPIC-025F` PR 5.2).

Same shape `settings_screen()` established (`EPIC-025E` PR 4.4e): a screen
leaves `AbstractScreenModule`'s ceremony for a plain `ScreenContribution`,
now owned by the bounded context whose screen it actually is rather than
carried by the shell as an unnamed strangler-period tenant
(`shell/legacy_screen_adapter.py`, retired in this same pull request).
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

DATABASE_ROUTE = "data_management"

_NAV = NavMetadata(
    title="Database",
    icon="database",
    section_sequence=10,
    item_sequence=20,
)


def _build_database_view() -> BaseView:
    """Builds the view, importing it only now — the same lazy shape every
    `ScreenContribution` factory in this codebase uses, so a headless
    `sync` run never imports Qt to answer a question it never asks."""
    from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_view import (
        DataManagementView,
    )

    return DataManagementView()


def _build_database_presenter(view: BaseView, container: IContainer) -> BasePresenter:
    from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_presenter import (
        DataManagementPresenter,
    )
    from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_view import (
        DataManagementView,
    )

    if not isinstance(view, DataManagementView):
        raise TypeError(
            f"the Database screen's presenter was handed a {type(view).__name__}, "
            "not a DataManagementView"
        )
    return DataManagementPresenter(view, container)


def database_screen() -> ScreenContribution:
    """`market_data`'s Database screen, described the way `settings_screen()`
    describes the shell's own screen."""
    return ScreenContribution(
        contributor_id="market_data",
        route=DATABASE_ROUTE,
        view_factory=_build_database_view,
        presenter_factory=_build_database_presenter,
        nav=_NAV,
    )
