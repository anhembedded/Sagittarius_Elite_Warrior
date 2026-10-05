"""The Developer mode as a contribution (`EPIC-033P`): the last mode on the
mode bar, and only under developer mode.

The shell contributes it, not a module: "what is about the application itself
belongs to the shell" (HLD §4, the Developer page of Tools → Options), and the
mode looks at every module's events at once. `gated_by` drops it, and any
command of its mode, in a normal run (`ContributionRegistry`). Lazy, as every
`ScreenContribution` must be: the factories are `Deferred` import paths.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.deferred import Deferred
from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import NavMetadata
from Sagittarius_Elite_Warrior.src.core.contracts.screen_contribution import (
    ScreenContribution,
)
from Sagittarius_Elite_Warrior.src.shell.surfaces import DEV_MODE_GATE

if TYPE_CHECKING:
    from sagittarius_engine.extensions.pyside_mvc import BasePresenter, BaseView

DEVELOPER_ROUTE = "developer"
#: After every module's mode: HLD §11.2.1 lists Developer last.
_NAV = NavMetadata(
    title="Developer",
    icon="eye",
    section_sequence=10,
    item_sequence=90,
)
_PACKAGE = "Sagittarius_Elite_Warrior.src.shell.developer_mode"
_VIEW: Deferred[BaseView] = Deferred(f"{_PACKAGE}.developer_view:DeveloperView")
_PRESENTER: Deferred[BasePresenter] = Deferred(
    f"{_PACKAGE}.developer_presenter:build_developer_presenter"
)


def developer_screen() -> ScreenContribution:
    return ScreenContribution(
        contributor_id="shell",
        route=DEVELOPER_ROUTE,
        view_factory=_VIEW,
        presenter_factory=_PRESENTER,
        nav=_NAV,
        gated_by=DEV_MODE_GATE,
    )
