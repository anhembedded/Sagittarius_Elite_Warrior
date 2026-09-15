"""`EPIC-016` — Dev Board's `ScreenModule`. Nav placement, and which
View/Presenter to build, unchanged from `main_window.py`'s old hard-coded
`_NAV_SECTIONS`/`_setup_router()`.

`EPIC-025` PR 1.4c-4 added one thing: this screen is a workbench surface, so
its View is handed what it needs to render the panels a *module* contributed —
the reading port and the container the factories take.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_table import (
    IContributionTable,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.registry import AbstractScreenModule
from sagittarius_engine.exceptions import DependencyResolutionError
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, BaseView
from sagittarius_engine.interfaces.i_container import IContainer


def _contribution_table(container: IContainer) -> IContributionTable | None:
    """The table, or `None` when this run has none.

    Both `None` cases are real, not defensive padding:

    - **Nothing bound it.** `assemble_contributions()` binds the port in the
      GUI entry point only; a container built without it raises
      `DependencyResolutionError`, which is the answer "this run has no
      surfaces", not a failure.
    - **A `Mock()` container.** The smoke tests that build every navigable
      route (`test_composition_root.py`,
      `test_environment_banner_all_screens.py`) pass one, and a `Mock` reaching
      a factory would build a `Mock` widget and place it on the screen. The
      `isinstance` check is what tells a real table from that.
    """
    try:
        table = container.resolve(IContributionTable)
    except DependencyResolutionError:
        return None
    return table if isinstance(table, IContributionTable) else None


class DashboardScreenModule(AbstractScreenModule):
    route = "dashboard"
    title = "Dev Board"
    icon = "layout-dashboard"
    section_key = "NAVIGATION"
    section_sequence = 10
    item_sequence = 10
    #: The screen `MainWindow` opens on boot — unchanged from `_DEFAULT_ROUTE`.
    is_default = True

    def create_view(self, container: IContainer) -> BaseView:
        from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view import (
            DashboardView,
        )

        return DashboardView(
            contributions=_contribution_table(container), container=container
        )

    def create_presenter(self, view: BaseView, container: IContainer) -> BasePresenter:
        from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_presenter import (
            DashboardPresenter,
        )

        return DashboardPresenter(view, container)
