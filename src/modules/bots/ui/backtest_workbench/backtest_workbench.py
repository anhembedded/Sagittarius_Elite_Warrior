"""`EPIC-040D` — the Backtest workbench: its page, coordinator and presenter, built from the ports.

Built once and kept while bots are selected; the Bots screen shows `page` in its Backtest tab
(`EPIC-040E`) and calls `follow` with the selection. The workbench names no kind: it asks the catalog
for a kind by id (`kinds`), and for that kind's editor (`editors`, one instance of its own, never the
Bots menu's), and runs the kind's own backtester through `RunBacktestQuery`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    BOT_MARKET,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_run_coordinator import (
    BacktestRunCoordinator,
    BacktestRunner,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench_presenter import (
    BacktestWorkbenchPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench_view import (
    DEFAULT_INTERVAL,
    BacktestWorkbenchView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.sandbox_editing import (
    KindSources,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.workbench_selection import (
    WorkbenchSelection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_kind_panel import (
    BotKindPanel,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    ICandleFeed,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

#: The result chart only draws what the backtest replayed; it never streams, so this owner never
#: subscribes to anything.
BACKTEST_CHART_OWNER = "bots.backtest"


@dataclass(frozen=True)
class WorkbenchPorts:
    """What the workbench is built from, for one venue (`BUG-172`): the sync and the result chart
    read that venue's market."""

    thread_manager: IThreadManager
    #: Runs `RunBacktestQuery` and nothing else: the host passes `lambda q: dispatcher.dispatch(
    #: RunBacktestQuery, q)`, so the page can reach no command (`EPIC-040D`).
    run_query: BacktestRunner
    sync: IMarketDataSync
    #: The venue's candle feed the result chart is built on (it only draws).
    feed: ICandleFeed
    #: How a backtest that could not run reaches the user (`BOT-169`).
    notifier: INotifier
    #: A kind by its id (the catalog's), and a new instance of its parameter editor.
    kinds: Callable[[str], IBotKind]
    editors: Callable[[str], BotKindPanel]
    market: MarketType = BOT_MARKET


class BacktestWorkbench:
    """@brief The Backtest workbench and what drives it."""

    def __init__(self, ports: WorkbenchPorts) -> None:
        self._view = BacktestWorkbenchView(
            LiveChartPorts(
                thread_manager=ports.thread_manager,
                feed=ports.feed,
                stream_owner=BACKTEST_CHART_OWNER,
                interval=DEFAULT_INTERVAL.value,
                market=ports.market,
                notifier=ports.notifier,
                scope=BOTS_ROUTE,
                live_commands=False,
            )
        )
        coordinator = BacktestRunCoordinator(
            ports.thread_manager, ports.run_query, ports.sync
        )
        self._presenter = BacktestWorkbenchPresenter(
            self._view,
            coordinator,
            ports.notifier,
            KindSources(ports.kinds, ports.editors),
        )

    @property
    def page(self) -> QWidget:
        return self._view

    @property
    def view(self) -> BacktestWorkbenchView:
        return self._view

    def follow(self, selection: WorkbenchSelection) -> None:
        self._presenter.follow(selection)

    def shutdown(self) -> None:
        self._presenter.shutdown()
