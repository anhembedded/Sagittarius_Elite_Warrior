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
    incidental."""

    trading_disabled: EmergencyStopStepResult
    orders_cancelled: EmergencyStopStepResult
    positions_closed: EmergencyStopStepResult

    @property
    def fully_succeeded(self) -> bool:
        return (
            self.trading_disabled.succeeded
            and self.orders_cancelled.succeeded
            and self.positions_closed.succeeded
        )
