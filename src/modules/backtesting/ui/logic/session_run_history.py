"""`BOT-095G` — session-scoped memory of the last few completed runs.

@details Without this, changing a parameter and running again permanently
discards the previous run's result — a trader comparing "EMA on 1m" against
"EMA on 5m" has to re-run the slower one from scratch just to look at it
again. This cache holds the last `MAX_HISTORY` completed runs in memory
(never on disk — a new process starts with an empty history, which is the
right default for a debugging/comparison aid, not a persisted artifact like
`BOT-115`'s `.sagi-report.json`).

@par Why a snapshot carries its own `klines`/`volume`
`BacktestRunConfig`/`BacktestResult` alone cannot redraw the candlestick
chart: a run's price data lives in the Presenter's transient
`_last_klines`/`_last_volume`, overwritten by the next run. Restoring an
older run with a different symbol or timeframe without its own copy would
either show the wrong candles or require a live re-fetch (a network round
trip mid-restore, which `state_persistence.restore()`'s own contract
already promises never happens: "opening the screen still runs nothing").
Bounded by `MAX_HISTORY` the same way the result/trades list already is —
this does not add a new order of magnitude of memory, only multiplies an
existing one by at most 5.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.state_scope import StateData

from .backtest_fsm_matrix import BacktestRunConfig


@dataclass(frozen=True)
class BacktestRunSnapshot:
    """One completed run, everything needed to redisplay it without
    touching the engine or the network again."""

    run_id: str
    timestamp: datetime
    form_data: StateData
    run_config: BacktestRunConfig
    result: BacktestResult
    klines: list = field(default_factory=list)
    volume: list = field(default_factory=list)

    @property
    def label(self) -> str:
        """A short, timestamped line for the history dropdown, e.g.
        `15:20 — ETHUSDT | 5m | ema_strategy | +28.4%`."""
        pnl = self.result.metrics.net_profit_percent if self.result.metrics else 0.0
        sign = "+" if pnl >= 0 else ""
        return (
            f"{self.timestamp.strftime('%H:%M:%S')} — "
            f"{self.run_config.to_summary_label()} — {sign}{pnl:.1f}%"
        )


def make_run_snapshot(
    *,
    form_data: StateData,
    run_config: BacktestRunConfig,
    result: BacktestResult,
    klines: list,
    volume: list,
    now: datetime,
) -> BacktestRunSnapshot:
    """`now` is a parameter, not `datetime.now()` inside this function, so a
    caller (and its tests) controls the timestamp instead of racing the
    clock — the same reasoning `BUG-123` already established for this
    screen's own mock kline grids."""
    return BacktestRunSnapshot(
        run_id=uuid.uuid4().hex,
        timestamp=now,
        form_data=form_data,
        run_config=run_config,
        result=result,
        klines=list(klines),
        volume=list(volume),
    )


class SessionRunHistoryCache:
    """In-memory ring of the last `MAX_HISTORY` completed runs, newest
    first. Never persisted — a fresh process starts empty."""

    MAX_HISTORY = 5

    def __init__(self) -> None:
        self._history: list[BacktestRunSnapshot] = []

    def push(self, snapshot: BacktestRunSnapshot) -> None:
        self._history.insert(0, snapshot)
        del self._history[self.MAX_HISTORY :]

    def get_all(self) -> tuple[BacktestRunSnapshot, ...]:
        return tuple(self._history)

    def get_by_id(self, run_id: str) -> BacktestRunSnapshot | None:
        for snapshot in self._history:
            if snapshot.run_id == run_id:
                return snapshot
        return None

    def clear(self) -> None:
        self._history.clear()
