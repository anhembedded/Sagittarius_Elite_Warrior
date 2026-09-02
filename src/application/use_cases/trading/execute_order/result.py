"""`EPIC-021G` — the outcome of one `ExecuteOrderCommand`."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.application.use_cases.queries.preview_order.order_preview import (
    OrderPreview,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.policies.trading_limit_policy import (
    TradingLimitCheck,
    TradingLimitContext,
    TradingLimitViolation,
)


class ExecuteOrderSafetyGate(str, Enum):
    """@brief The three checks `EPIC-021G` §2.3 requires before any order
    submission — independent of, and evaluated before, the four
    `TradingLimitViolation` checks."""

    TRADING_VENUE_DISABLED = "trading_venue_disabled"
    TRADING_SWITCH_OFF = "trading_switch_off"
    CONNECTION_NOT_READY = "connection_not_ready"


@dataclass(frozen=True)
class ExecuteOrderResult:
    """@details `blocked_by` is a safety gate, a trading-limit violation,
    or `None` (nothing blocked it). `preview`/`limit_checks` are populated
    as far as evaluation got — a safety-gate block never reaches order
    normalization, so both stay empty/`None` in that case, matching
    `EPIC-021G` §5's own worked examples (a limit-check block shows every
    check; a safety-gate block shows none of them).
    """

    blocked_by: ExecuteOrderSafetyGate | TradingLimitViolation | None
    preview: OrderPreview | None
    limit_checks: tuple[TradingLimitCheck, ...]
    submitted_order: Order | None
    #: The raw numbers `limit_checks` was evaluated against — `None`
    #: exactly when `limit_checks` is empty (a safety-gate block). Exists
    #: so a formatter (`trade-once`'s own worked display, e.g. "lệnh
    #: 1/20") never has to recompute what the handler already knows,
    #: risking drift between the decision and what gets shown for it.
    limit_context: TradingLimitContext | None = None

    @property
    def blocked(self) -> bool:
        return self.blocked_by is not None
