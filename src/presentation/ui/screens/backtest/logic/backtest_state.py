from __future__ import annotations

from enum import Enum


class BacktestUiState(str, Enum):
    """
    @brief FSM states for the Backtest Screen (BOT-059).

    @details
    A dedicated enum instead of the shared `UIMode` (Dashboard/Data
    Management) — Backtest is the only screen with a distinct "syncing
    market data before/instead of running" state, and bolting an
    `isSyncing: bool` flag onto `UIMode` would let the UI represent
    contradictory combinations (e.g. LOCKED + isSyncing) that a state
    machine transition table rules out by construction.

    Named `BacktestUiState`, not `BacktestState`, to avoid colliding with
    the unrelated `BacktestState` singleton-flag class already in
    `application/use_cases/backtest/run_backtest/handler.py` (dynamic/replay
    engine, a different layer and a different concept entirely).
    """

    IDLE = "IDLE"
    RUNNING = "RUNNING"
    SYNCING = "SYNCING"
    ERROR = "ERROR"
