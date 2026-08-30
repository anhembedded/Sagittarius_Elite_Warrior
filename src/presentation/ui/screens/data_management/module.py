"""`EPIC-016` — Database screen's `ScreenModule`."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.registry import AbstractScreenModule
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, BaseView
from sagittarius_engine.interfaces.i_container import IContainer


class DatabaseScreenModule(AbstractScreenModule):
    route = "data_management"
    title = "Database"
    icon = "database"
    section_key = "NAVIGATION"
    section_sequence = 10
    item_sequence = 20

    def create_view(self, container: IContainer) -> BaseView:
        from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view import (
            DataManagementView,
        )

        return DataManagementView()

    def create_presenter(self, view: BaseView, container: IContainer) -> BasePresenter:
        from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_presenter import (
            DataManagementPresenter,
        )

        return DataManagementPresenter(view, container)
