"""Coordinators for the Backtest screen (`EPIC-003E`).

`BackTestPresenter` was 2,542 lines across 111 methods — the largest class
in the codebase. These coordinators take the business workflows out of it
so the presenter is left orchestrating: FSM transitions, signal binding,
and action ownership.

Each coordinator follows the pattern `EPIC-003B` proved on
`DataManagementPresenter`: it receives what it needs through its
constructor — the view model, plain callables for signals and state — and
never resolves the container or reaches back into the presenter.
"""

from __future__ import annotations

from .chart_render_coordinator import ChartRenderCoordinator
from .data_sync_coordinator import DataSyncCoordinator
from .execution_coordinator import ExecutionCoordinator
from .factory import Coordinators, build_coordinators
from .indicator_coordinator import IndicatorCoordinator
from .strategy_config_coordinator import StrategyConfigCoordinator
from .trade_log_coordinator import TradeLogCoordinator

__all__ = [
    "ChartRenderCoordinator",
    "Coordinators",
    "DataSyncCoordinator",
    "ExecutionCoordinator",
    "IndicatorCoordinator",
    "StrategyConfigCoordinator",
    "TradeLogCoordinator",
    "build_coordinators",
]
