"""`EPIC-021I` — Trading screen's `ScreenModule`."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.registry import AbstractScreenModule
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, BaseView
from sagittarius_engine.interfaces.i_container import IContainer


class TradingScreenModule(AbstractScreenModule):
    route = "trading"
    title = "Giao dịch"
    icon = "chart-candlestick"
    section_key = "NAVIGATION"
    section_sequence = 10
    #: Between Dashboard (10) and Data Management (20).
    item_sequence = 15

    def create_view(self, container: IContainer) -> BaseView:
        from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.trading_view import (
            TradingView,
        )

        return TradingView()

    def create_presenter(self, view: BaseView, container: IContainer) -> BasePresenter:
        from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.trading_presenter import (
            TradingPresenter,
        )

        return TradingPresenter(view, container)
