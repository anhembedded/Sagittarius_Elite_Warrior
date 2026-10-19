"""`EPIC-024B` §0 — the outcome of one `CancelOrderCommand`."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order


@dataclass(frozen=True)
class CancelOrderResult:
    """@details Reuses `ExecuteOrderSafetyGate` rather than a duplicate
    enum with the same three members — cancelling a real order is gated
    behind the exact same three checks placing one is (`EPIC-024B` §4:
    the three safety layers apply automatically, not just to submission).
    """

    blocked_by: ExecuteOrderSafetyGate | None
    cancelled_order: Order | None
    #: The exchange holds no such order (unknown-order refusal): it filled, ended or was cancelled
    #: already. A value, not an exception, so the command dispatcher does not log an expected
    #: outcome as a failed command (`BUG-226`). `cancelled_order` is `None` with it.
    already_gone: bool = False

    @property
    def blocked(self) -> bool:
        return self.blocked_by is not None
