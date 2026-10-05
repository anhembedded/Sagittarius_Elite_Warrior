"""`EPIC-033D` — a Backtest presenter's Run and Stop, bound as the window
binds them (`tests/command_actions.py`), for the presenter's own tests."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QAction
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_commands import (
    RUN,
    STOP,
    backtest_commands,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_presenter import (
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_screen import (
    BACKTEST_ROUTE,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions


@dataclass(frozen=True)
class BacktestActions:
    run: QAction
    stop: QAction


def backtest_actions(presenter: BackTestPresenter) -> BacktestActions:
    registry = bound_actions(
        presenter.view, backtest_commands(BACKTEST_ROUTE), presenter.bind_commands
    )
    return BacktestActions(registry.action(RUN), registry.action(STOP))
