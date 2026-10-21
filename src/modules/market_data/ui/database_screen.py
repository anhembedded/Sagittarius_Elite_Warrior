"""The Database (Data Management) screen as a contribution — `market_data`'s
own (`EPIC-025F` PR 5.2).

The `ScreenContribution` shape (`EPIC-025E` PR 4.4e): a screen
leaves `AbstractScreenModule`'s ceremony for a plain `ScreenContribution`,
now owned by the bounded context whose screen it actually is rather than
carried by the shell as an unnamed strangler-period tenant
(`shell/legacy_screen_adapter.py`, retired in this same pull request).

Lazy, as every `ScreenContribution` must be: the factories are `Deferred` import paths
(`BOT-148`), so a headless `sync` run never imports Qt to answer a question it never asks.
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

DATABASE_ROUTE = "data_management"

_NAV = NavMetadata(
    title="Data",
    access_key="d",
    icon="database",
    section_sequence=10,
    item_sequence=20,
)


_PACKAGE = "Sagittarius_Elite_Warrior.src.modules.market_data.ui"
_VIEW: Deferred[BaseView] = Deferred(
    f"{_PACKAGE}.data_management_view:DataManagementView"
)
_PRESENTER: Deferred[BasePresenter] = Deferred(
    f"{_PACKAGE}.data_management_presenter:DataManagementPresenter"
)


def database_screen() -> ScreenContribution:
    """`market_data`'s Database screen, as a `ScreenContribution`."""
    return ScreenContribution(
        contributor_id="market_data",
        route=DATABASE_ROUTE,
        view_factory=_VIEW,
        presenter_factory=_PRESENTER,
        nav=_NAV,
    )
