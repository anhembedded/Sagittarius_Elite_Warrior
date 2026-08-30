"""`EPIC-016` — Dev Board's `ScreenModule`. Nav placement, and which
View/Presenter to build, unchanged from `main_window.py`'s old hard-coded
`_NAV_SECTIONS`/`_setup_router()`."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.registry import AbstractScreenModule
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, BaseView
from sagittarius_engine.interfaces.i_container import IContainer


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

        return DashboardView()

    def create_presenter(self, view: BaseView, container: IContainer) -> BasePresenter:
        from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_presenter import (
            DashboardPresenter,
        )

        return DashboardPresenter(view, container)
