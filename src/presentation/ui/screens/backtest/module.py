"""`EPIC-016` — Backtest screen's `ScreenModule`."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.registry import AbstractScreenModule
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, BaseView
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_container import IContainer


class BacktestScreenModule(AbstractScreenModule):
    route = "backtest"
    title = "Backtest Engine"
    icon = "bar-chart-2"
    section_key = "QUANT ENGINE"
    section_sequence = 20
    item_sequence = 10

    def create_view(self, container: IContainer) -> BaseView:
        # `build_backtest_view`, not `BackTestView()` (`EPIC-013F`): which
        # View this install uses is a named choice read from config, and the
        # factory's return type says what the router may do with it. Read
        # once, here — a View is never swapped while the app runs.
        from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.view_factory import (
            build_backtest_view,
        )

        config = container.resolve(IConfig)
        return build_backtest_view(config)

    def create_presenter(self, view: BaseView, container: IContainer) -> BasePresenter:
        from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
            BackTestPresenter,
        )

        return BackTestPresenter(view, container)
