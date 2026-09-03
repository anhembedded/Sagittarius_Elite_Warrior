"""`EPIC-021K` — the outcome of one `EmergencyStopCommand`.

@details A step can fail (network loss, the exchange rejecting a close,
insufficient margin) — reporting that as a bare `bool` would be the exact
"lời nói dối nguy hiểm nhất" (the most dangerous lie) the task's own
design section names: a button that says "stopped" while a position is
still open. Each step gets its own `EmergencyStopStepResult` (`succeeded`
+ a human `detail`, never `succeeded` alone), the same "never a bare bool"
idiom `EnableTradingResult`/`EnableTradingBlockReason` already established
for this app's other safety-critical outcome.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.domain.trading.live_position import LivePosition
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order


@dataclass(frozen=True)
class EmergencyStopStepResult:
    """One step's outcome. `detail` is always populated — a human-readable
    summary of what happened (`"2 lệnh đã huỷ"`, `"APIError(-2019) Margin
    is insufficient"`), never left for the caller to infer from `succeeded`
    alone."""

    succeeded: bool
    detail: str


@dataclass(frozen=True)
class EmergencyStopResult:
    """The three steps, in the order they were attempted — see
    `EmergencyStopCommandHandler.execute()` for why that order is not
    incidental.

    @details `BUG-093` — `final_positions`/`final_open_orders` are a
    best-effort read of the account's *true* state, taken after the three
    steps above regardless of their own outcome: the user-data stream is
    already stopped by step 1, so nothing will otherwise correct a UI that
    seeded its tables before this command ran. `final_state_confirmed` is
    `False` only when that read itself failed (a caller must not treat
    empty `final_positions`/`final_open_orders` as "confirmed flat" in
    that case — it means "unknown", not "zero")."""

    trading_disabled: EmergencyStopStepResult
    orders_cancelled: EmergencyStopStepResult
    positions_closed: EmergencyStopStepResult
    final_positions: tuple[LivePosition, ...] = ()
    final_open_orders: tuple[Order, ...] = ()
    final_state_confirmed: bool = False

    @property
    def fully_succeeded(self) -> bool:
        return (
            self.trading_disabled.succeeded
            and self.orders_cancelled.succeeded
            and self.positions_closed.succeeded
        )
