"""`EPIC-029D` — what a backtest request answers when no replay ran."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    GridBacktestCancelled,
    GridBacktestResult,
)


@dataclass(frozen=True, slots=True)
class GridBacktestRefusal:
    """Why nothing was replayed, in words the screen shows.

    `missing_candles` says the period's candles are not stored: the screen
    offers to sync them, and never fetches on its own (`BUG-107`)."""

    reason: str
    missing_candles: bool = False


type GridBacktestAnswer = (
    GridBacktestResult | GridBacktestCancelled | GridBacktestRefusal
)
