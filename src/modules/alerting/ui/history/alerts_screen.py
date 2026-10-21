"""The Alerts screen as a contribution (`EPIC-036D2`): what the app has told the owner.

`alerting` contributes it: the history is the module's own subject. Lazy, as every
`ScreenContribution` must be: the factories are `Deferred` import paths.
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

ALERTS_ROUTE = "alerts"
#: After the Bots mode and before Developer (item 90).
_NAV = NavMetadata(
    title="Alerts", icon="bell", section_sequence=10, item_sequence=80, access_key="a"
)
_PACKAGE = "Sagittarius_Elite_Warrior.src.modules.alerting.ui.history"
_VIEW: Deferred[BaseView] = Deferred(f"{_PACKAGE}.alerts_view:AlertsView")
_PRESENTER: Deferred[BasePresenter] = Deferred(
    f"{_PACKAGE}.alerts_presenter:build_alerts_presenter"
)


def alerts_screen() -> ScreenContribution:
    return ScreenContribution(
        contributor_id="alerting",
        route=ALERTS_ROUTE,
        view_factory=_VIEW,
        presenter_factory=_PRESENTER,
        nav=_NAV,
    )
