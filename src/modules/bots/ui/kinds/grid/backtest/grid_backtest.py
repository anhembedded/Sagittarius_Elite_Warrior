"""`EPIC-029D` — the Grid's `BotBacktest`: its page, coordinator and presenter.

Built by `kind_panels.backtest_for("grid")` when a Grid bot is selected; the
screen shows `page` in the detail panel's Backtest tab and calls `follow`.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_backtest import (
    BacktestContext,
    BacktestPorts,
    BotBacktest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.grid_backtest_coordinator import (
    GridBacktestCoordinator,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.grid_backtest_presenter import (
    GridBacktestPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.grid_backtest_view import (
    GridBacktestView,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)

#: The result chart only draws what the backtest replayed; it never streams,
#: so this owner never subscribes to anything.
BACKTEST_CHART_OWNER = "bots.backtest"


class GridBacktest(BotBacktest):
    """@brief The Grid backtest page and what drives it."""

    def __init__(self, ports: BacktestPorts) -> None:
        self._view = GridBacktestView(
            LiveChartPorts(
                thread_manager=ports.thread_manager,
                feed=ports.feed,
                stream_owner=BACKTEST_CHART_OWNER,
                interval="15m",
                market=MarketType.SPOT,
            )
        )
        coordinator = GridBacktestCoordinator(
            ports.thread_manager, ports.dispatcher, ports.sync
        )
        self._presenter = GridBacktestPresenter(self._view, coordinator)

    @property
    def page(self) -> QWidget:
        return self._view

    @property
    def view(self) -> GridBacktestView:
        return self._view

    def follow(self, context: BacktestContext | None) -> None:
        self._presenter.follow(context)

    def shutdown(self) -> None:
        self._presenter.shutdown()
