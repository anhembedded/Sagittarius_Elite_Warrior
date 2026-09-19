"""The Dev Board (Dashboard) screen as a contribution — `trading`'s own
(`EPIC-025F` PR 5.2).

Same shape `settings_screen()` established (`EPIC-025E` PR 4.4e), with one
real difference from every other screen converted this way: `DashboardView`
needs `container` at *view* construction (`_contribution_table(container)`,
to read every module's `DEV_PROBE` contributions), not only at presenter
construction the way `ScreenContribution.presenter_factory` already supplies
it. `PresenterManager.navigate_to()` calls `view_factory()` with zero
arguments — a hard constraint from the Engine, not negotiable here — so the
container has to be closed over at the point the `ScreenContribution` itself
is built, i.e. inside `dashboard_screen(container)` rather than inside a
module-level `_build_dashboard_view()`. `TradingModule.boot()` stashes
`context.container` for exactly this call — not `register()`, whose own
`context.container` is a permanently resolve-refusing spy (`TradingModule.
boot()`'s own docstring has the full reasoning) — the same single container
instance every screen ultimately runs against (the app has exactly one for
its whole lifetime — `AbstractScreenModule.build_descriptor()`'s own former
docstring said so, and this is the same fact, reached one hook earlier).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_table import (
    IContributionTable,
)
from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import NavMetadata
from Sagittarius_Elite_Warrior.src.core.contracts.screen_contribution import (
    ScreenContribution,
)
from sagittarius_engine.exceptions import DependencyResolutionError

if TYPE_CHECKING:
    from sagittarius_engine.extensions.pyside_mvc import BasePresenter, BaseView
    from sagittarius_engine.interfaces.i_container import IContainer

DASHBOARD_ROUTE = "dashboard"

#: **Not** the default (`EPIC-025` PR 1.5a, ADR D13): the app opens on
#: Welcome, not on a developer testbed that happened to be first in the
#: sidebar.
_NAV = NavMetadata(
    title="Dev Board",
    icon="layout-dashboard",
    section_sequence=10,
    item_sequence=10,
)


def _contribution_table(container: IContainer) -> IContributionTable | None:
    """The table, or `None` when this run has none.

    Both `None` cases are real, not defensive padding (unchanged from
    `DashboardScreenModule`'s own docstring):

    - **Nothing bound it.** `assemble_contributions()` binds the port in the
      GUI entry point only; a container built without it raises
      `DependencyResolutionError`, which is the answer "this run has no
      surfaces", not a failure.
    - **A `Mock()` container.** The smoke tests that build every navigable
      route pass one, and a `Mock` reaching a factory would build a `Mock`
      widget and place it on the screen. The `isinstance` check is what
      tells a real table from that.
    """
    try:
        table = container.resolve(IContributionTable)
    except DependencyResolutionError:
        return None
    return table if isinstance(table, IContributionTable) else None


def _build_dashboard_presenter(view: BaseView, container: IContainer) -> BasePresenter:
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dashboard_presenter import (
        DashboardPresenter,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dashboard_view import (
        DashboardView,
    )

    if not isinstance(view, DashboardView):
        raise TypeError(
            f"the Dev Board screen's presenter was handed a {type(view).__name__}, "
            "not a DashboardView"
        )
    return DashboardPresenter(view, container)


def dashboard_screen(container: IContainer) -> ScreenContribution:
    """`trading`'s Dev Board screen. Takes `container` (unlike every other
    `*_screen()` factory in this codebase) for the reason this module's own
    docstring explains: `DashboardView` needs it at construction time, and
    the Engine's router calls `view_factory()` with no arguments."""

    def _build_dashboard_view() -> BaseView:
        from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dashboard_view import (
            DashboardView,
        )

        return DashboardView(
            contributions=_contribution_table(container), container=container
        )

    return ScreenContribution(
        contributor_id="trading",
        route=DASHBOARD_ROUTE,
        view_factory=_build_dashboard_view,
        presenter_factory=_build_dashboard_presenter,
        nav=_NAV,
    )
