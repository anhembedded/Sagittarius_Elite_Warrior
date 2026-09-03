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


class ExecuteOrderNotionalRejection(str, Enum):
    """@brief `BUG-090` — the order's notional (after step-size rounding)
    doesn't clear the exchange's own `minNotional` filter. Distinct from
    `TradingLimitViolation`: the four session limits are configurable
    safety policy this app chooses to enforce; this is Binance's own hard
    requirement, computed once already by `PreviewOrderQueryHandler`
    (`OrderPreview.notional_check`) — checked here so the app refuses
    before a network round-trip instead of relying on the exchange's own
    `-4164` rejection every time (`EPIC-021`'s own §1 finding 6: the
    parser/policy for this existed since `BOT-095E1` and was never wired
    into the live order path)."""

    MIN_NOTIONAL = "min_notional"


@dataclass(frozen=True)
class ExecuteOrderResult:
    """@details `blocked_by` is a safety gate, a notional rejection, a
    trading-limit violation, or `None` (nothing blocked it). `preview`/
    `limit_checks` are populated as far as evaluation got — a safety-gate
    block never reaches order normalization, so both stay empty/`None` in
    that case, matching `EPIC-021G` §5's own worked examples (a limit-check
    block shows every check; a safety-gate block shows none of them). A
    `MIN_NOTIONAL` block has a `preview` (normalization already ran to
    compute it) but an empty `limit_checks` — the four session limits were
    never reached.
    """

    blocked_by: (
        ExecuteOrderSafetyGate
        | ExecuteOrderNotionalRejection
        | TradingLimitViolation
        | None
    )
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
