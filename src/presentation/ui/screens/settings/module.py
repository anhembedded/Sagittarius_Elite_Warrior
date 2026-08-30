"""`EPIC-016` — Settings screen's `ScreenModule`."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.registry import (
    AbstractScreenModule,
    NavLocation,
)
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, BaseView
from sagittarius_engine.interfaces.i_container import IContainer


class SettingsScreenModule(AbstractScreenModule):
    route = "settings"
    title = "API & Credentials"
    icon = "settings"
    #: Ghim đáy sidebar — unchanged from `_BOTTOM_ACTIONS`.
    location = NavLocation.BOTTOM_ACTION
    item_sequence = 10

    def create_view(self, container: IContainer) -> BaseView:
        from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.settings_view import (
            SettingsView,
        )

        return SettingsView()

    def create_presenter(self, view: BaseView, container: IContainer) -> BasePresenter:
        from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.settings_presenter import (
            SettingsPresenter,
        )

        return SettingsPresenter(view, container)
