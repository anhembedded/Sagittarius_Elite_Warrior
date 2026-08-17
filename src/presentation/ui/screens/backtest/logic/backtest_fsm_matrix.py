from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.value_objects.currency import Currency
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


class BacktestUiState(str, Enum):
    """
    @brief FSM States for the Backtest Screen (BOT-095B).
    @details
    Single source of truth for all lifecycle phases of the Backtest UI:
    - IDLE: Initial state or clean reset.
    - CONFIG_DIRTY: User changed toolbar inputs after running; results below are stale.
    - RUNNING: Actively calculating backtest in background thread.
    - CANCELLING: User requested cancellation; waiting for worker to stop cleanly.
    - SYNCING: Actively syncing market data from Binance.
    - EMPTY_DATA: Calculation finished with zero trades or empty historical data.
    - COMPLETED: Calculation finished successfully; results match toolbar parameters.
    - ERROR: System exception occurred during calculation or sync.
    """

    IDLE = "IDLE"
    CONFIG_DIRTY = "CONFIG_DIRTY"
    RUNNING = "RUNNING"
    CANCELLING = "CANCELLING"
    SYNCING = "SYNCING"
    EMPTY_DATA = "EMPTY_DATA"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class BacktestUiEvent(str, Enum):
    """
    @brief FSM Events dispatched to trigger state transitions (BOT-095B).
    """

    CONFIG_CHANGED = "CONFIG_CHANGED"
    CONFIG_RESTORED = "CONFIG_RESTORED"
    RUN_REQUESTED = "RUN_REQUESTED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    SYNC_REQUESTED = "SYNC_REQUESTED"
    BACKTEST_SUCCEEDED = "BACKTEST_SUCCEEDED"
    BACKTEST_EMPTY = "BACKTEST_EMPTY"
    BACKTEST_CANCELLED = "BACKTEST_CANCELLED"
    BACKTEST_CANCELLED_TO_CONFIG_DIRTY = "BACKTEST_CANCELLED_TO_CONFIG_DIRTY"
    BACKTEST_CANCELLED_TO_COMPLETED = "BACKTEST_CANCELLED_TO_COMPLETED"
    BACKTEST_FAILED = "BACKTEST_FAILED"
    SYNC_SUCCEEDED = "SYNC_SUCCEEDED"
    SYNC_FAILED = "SYNC_FAILED"
    ERROR_DISMISSED = "ERROR_DISMISSED"


class BacktestActionKind(str, Enum):
    """Kinds of background work that may own the Backtest UI lifecycle."""

    BACKTEST = "BACKTEST"
    SYNC = "SYNC"


class BacktestActionOutcome(str, Enum):
    """The terminal outcome currently owned by a Backtest action."""

    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    EMPTY = "EMPTY"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INVALIDATED = "INVALIDATED"


#: Declarative State Transition Matrix: (CurrentState, Event) -> NextState
BACKTEST_STATE_TRANSITIONS: dict[
    tuple[BacktestUiState, BacktestUiEvent], BacktestUiState
] = {
    # --- IDLE ---
    (BacktestUiState.IDLE, BacktestUiEvent.CONFIG_CHANGED): BacktestUiState.IDLE,
    (BacktestUiState.IDLE, BacktestUiEvent.RUN_REQUESTED): BacktestUiState.RUNNING,
    (BacktestUiState.IDLE, BacktestUiEvent.SYNC_REQUESTED): BacktestUiState.SYNCING,
    # --- COMPLETED ---
    (
        BacktestUiState.COMPLETED,
        BacktestUiEvent.CONFIG_CHANGED,
    ): BacktestUiState.CONFIG_DIRTY,
    (BacktestUiState.COMPLETED, BacktestUiEvent.RUN_REQUESTED): BacktestUiState.RUNNING,
    (
        BacktestUiState.COMPLETED,
        BacktestUiEvent.SYNC_REQUESTED,
    ): BacktestUiState.SYNCING,
    # --- CONFIG_DIRTY (Stale Data) ---
    (
        BacktestUiState.CONFIG_DIRTY,
        BacktestUiEvent.CONFIG_CHANGED,
    ): BacktestUiState.CONFIG_DIRTY,
    (
        BacktestUiState.CONFIG_DIRTY,
        BacktestUiEvent.CONFIG_RESTORED,
    ): BacktestUiState.COMPLETED,
    (
        BacktestUiState.CONFIG_DIRTY,
        BacktestUiEvent.RUN_REQUESTED,
    ): BacktestUiState.RUNNING,
    (
        BacktestUiState.CONFIG_DIRTY,
        BacktestUiEvent.SYNC_REQUESTED,
    ): BacktestUiState.SYNCING,
    # --- RUNNING ---
    (
        BacktestUiState.RUNNING,
        BacktestUiEvent.CANCEL_REQUESTED,
    ): BacktestUiState.CANCELLING,
    (
        BacktestUiState.RUNNING,
        BacktestUiEvent.BACKTEST_SUCCEEDED,
    ): BacktestUiState.COMPLETED,
    (
        BacktestUiState.RUNNING,
        BacktestUiEvent.BACKTEST_EMPTY,
    ): BacktestUiState.EMPTY_DATA,
    (BacktestUiState.RUNNING, BacktestUiEvent.BACKTEST_FAILED): BacktestUiState.ERROR,
    # --- CANCELLING ---
    (
        BacktestUiState.CANCELLING,
        BacktestUiEvent.BACKTEST_CANCELLED,
    ): BacktestUiState.IDLE,
    (
        BacktestUiState.CANCELLING,
        BacktestUiEvent.BACKTEST_CANCELLED_TO_CONFIG_DIRTY,
    ): BacktestUiState.CONFIG_DIRTY,
    (
        BacktestUiState.CANCELLING,
        BacktestUiEvent.BACKTEST_CANCELLED_TO_COMPLETED,
    ): BacktestUiState.COMPLETED,
    (BacktestUiState.CANCELLING, BacktestUiEvent.BACKTEST_FAILED): BacktestUiState.IDLE,
    # --- SYNCING ---
    (BacktestUiState.SYNCING, BacktestUiEvent.SYNC_SUCCEEDED): BacktestUiState.RUNNING,
    (BacktestUiState.SYNCING, BacktestUiEvent.SYNC_FAILED): BacktestUiState.ERROR,
    # --- EMPTY_DATA ---
    (
        BacktestUiState.EMPTY_DATA,
        BacktestUiEvent.SYNC_REQUESTED,
    ): BacktestUiState.SYNCING,
    (BacktestUiState.EMPTY_DATA, BacktestUiEvent.CONFIG_CHANGED): BacktestUiState.IDLE,
    (
        BacktestUiState.EMPTY_DATA,
        BacktestUiEvent.RUN_REQUESTED,
    ): BacktestUiState.RUNNING,
    # --- ERROR ---
    (BacktestUiState.ERROR, BacktestUiEvent.ERROR_DISMISSED): BacktestUiState.IDLE,
    (BacktestUiState.ERROR, BacktestUiEvent.CONFIG_CHANGED): BacktestUiState.IDLE,
    (BacktestUiState.ERROR, BacktestUiEvent.RUN_REQUESTED): BacktestUiState.RUNNING,
    (BacktestUiState.ERROR, BacktestUiEvent.SYNC_REQUESTED): BacktestUiState.SYNCING,
}

#: UI Modes in which controls must be disabled
DISABLED_UI_MODES: frozenset[str] = frozenset(
    {
        BacktestUiState.RUNNING.value,
        BacktestUiState.CANCELLING.value,
        BacktestUiState.SYNCING.value,
    }
)


@dataclass(frozen=True)
class BacktestRunConfig:
    """
    @brief Immutable snapshot of toolbar parameters for one run (BOT-095B).
    @details
    Used for Dirty Tracking: Comparing the current toolbar state against the
    last executed run snapshot to detect stale results and compute diffs.
    """

    strategy_key: str
    timeframe: TimeFrame
    initial_balance: float
    start_time: datetime | None
    end_time: datetime | None
    strategy_params: dict[str, Any] | None = field(default=None)
    currency: Currency = Currency.USD
    symbol: str = "ETHUSDT"

    def compute_diff_summary(self, other: BacktestRunConfig) -> str:
        """
        @brief Compute a human-readable description of changed fields.
        """
        diffs: list[str] = []

        if self.timeframe != other.timeframe:
            diffs.append(
                f"Khung thời gian ({self.timeframe.value} → {other.timeframe.value})"
            )

        if self.strategy_key != other.strategy_key:
            diffs.append(f"Chiến lược ({self.strategy_key} → {other.strategy_key})")

        if abs(self.initial_balance - other.initial_balance) > 1e-6:
            diffs.append(
                f"Vốn ({self.initial_balance:,.0f} → {other.initial_balance:,.0f})"
            )

        if self.currency != other.currency:
            diffs.append(f"Tiền tệ ({self.currency.value} → {other.currency.value})")

        if self.start_time != other.start_time or self.end_time != other.end_time:
            self_start = (
                self.start_time.strftime("%Y-%m-%d") if self.start_time else "Đầu"
            )
            self_end = (
                self.end_time.strftime("%Y-%m-%d") if self.end_time else "Hiện tại"
            )
            other_start = (
                other.start_time.strftime("%Y-%m-%d") if other.start_time else "Đầu"
            )
            other_end = (
                other.end_time.strftime("%Y-%m-%d") if other.end_time else "Hiện tại"
            )
            diffs.append(
                f"Khoảng thời gian ({self_start}..{self_end} → {other_start}..{other_end})"
            )

        if self.strategy_params != other.strategy_params:
            diffs.append("Thông số Chiến lược")

        if not diffs:
            return "Cấu hình đã thay đổi"

        return ", ".join(diffs)

    def to_summary_label(self) -> str:
        """
        @brief Generate a concise single-line summary of the executed run.
        """
        return f"{self.symbol} | {self.timeframe.value} | {self.strategy_key} | Vốn: {self.initial_balance:,.0f} {self.currency.value}"


@dataclass(frozen=True)
class BacktestActionContext:
    """Immutable owner record for one submitted background action."""

    action_id: int
    kind: BacktestActionKind
    config: BacktestRunConfig
    started_at: datetime
    previous_state: BacktestUiState
