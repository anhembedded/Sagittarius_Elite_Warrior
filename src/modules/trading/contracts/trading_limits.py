"""The four session limits as published vocabulary — what was checked, against
what, and which one refused (`EPIC-021G`; published `EPIC-025` PR 2.1g).

@details These four types crossed this module's boundary from the day
`ExecuteOrderResult` was published: that DTO carries `limit_checks: tuple[
TradingLimitCheck, ...]`, a `TradingLimitViolation` inside its `blocked_by`
union, and the `TradingLimitContext` the checks were judged against — so a
consumer reading the answer had to import all three out of
`domain/policies/trading_limit_policy.py`. Three files outside the module did
exactly that (`trade-once`'s command and its formatter, and the shared
`execute_order_block_reason`), each as a counted boundary violation.

Same measurement, same answer as PR 2.1a's `OrderIntent` and PR 2.1d's
`OrderQuantityRoundingPolicy`: what a module's `contracts/` holds is what
crosses its boundary, and these already did. `TradingLimitPolicy` — the
evaluator, the thing that *decides* — stays in `domain/policies/`, where
nothing outside the module may reach it. That is the line: the answer is
published, the judgement is not.

@par Why `TradingLimits` is here too, and not only the answer types
It is the thresholds the caller is *shown*, not a rule: `trade-once` prints
"notional 128.20 ≤ 500 ✔", and the numbers on both sides of that comparison
have to come from the same place the policy used, or the display drifts from
the decision. `ExecuteOrderResult.limits` carries them for exactly that
reason, which is also what let PR 2.1g delete the CLI's `container.resolve(
TradingLimitPolicy)` — a presentation file resolving a domain policy to read
one attribute off it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_purpose import (
    OrderPurpose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetFacts,
)


class TradingLimitViolation(str, Enum):
    """@brief Which limit blocked an order — one of the four signal limits,
    or one of a budgeted owner's checks (`EPIC-029`) — named so a
    caller (and a human reading a log line) never has to infer it from a
    bare `False`."""

    MAX_ORDERS_PER_SESSION = "max_orders_per_session"
    MAX_NOTIONAL_PER_ORDER = "max_notional_per_order"
    MAX_POSITIONS_PER_SYMBOL = "max_positions_per_symbol"
    MIN_ORDER_INTERVAL = "min_order_interval"
    #: `EPIC-029` ADR D6 — a budgeted owner's five checks, which replace the
    #: three signal limits above for its orders (`OwnerBudget`)...
    OWNER_BUDGET_OPEN_ORDERS = "owner_budget_open_orders"
    OWNER_BUDGET_EXPOSURE = "owner_budget_exposure"
    OWNER_BUDGET_SELL_EXCEEDS_INVENTORY = "owner_budget_sell_exceeds_inventory"
    OWNER_BUDGET_SPACING = "owner_budget_spacing"
    OWNER_BUDGET_RATE = "owner_budget_rate"
    #: ...and the sixth gate: an order carrying a client order tag with no
    #: budget registered for it on the order's symbol, so a bot never falls
    #: back to the signal limits, which have no inventory check.
    OWNER_BUDGET_MISSING = "owner_budget_missing"


#: The four limits every order without a budget is checked against, in the
#: order they are reported.
SIGNAL_LIMITS = (
    TradingLimitViolation.MAX_ORDERS_PER_SESSION,
    TradingLimitViolation.MAX_NOTIONAL_PER_ORDER,
    TradingLimitViolation.MAX_POSITIONS_PER_SYMBOL,
    TradingLimitViolation.MIN_ORDER_INTERVAL,
)


@dataclass(frozen=True)
class TradingLimits:
    """Configured thresholds — see `ConfigKeys.TRADING_MAX_ORDERS_PER_SESSION`
    et al. for where these come from at runtime."""

    max_orders_per_session: int
    max_notional_per_order: Decimal
    max_positions_per_symbol: int
    min_order_interval: timedelta


@dataclass(frozen=True)
class TradingLimitContext:
    """The live, per-attempt facts `TradingLimitPolicy` checks against
    `TradingLimits`. Sourced from `TradingSessionState`, never from a
    fresh network call per order — reconciliation happens once, at
    `EnableTradingCommand` time (`ADR §4`)."""

    orders_sent_this_session: int
    order_notional: Decimal
    open_position_count_for_symbol: int
    time_since_last_order_for_symbol: timedelta | None
    #: `EPIC-028I` — a protective order passes every limit (`OrderPurpose`).
    purpose: OrderPurpose = OrderPurpose.ENTRY
    #: `EPIC-029` ADR D5 — the order's client order tag, `None` for an
    #: untagged order (manual, strategy).
    client_order_tag: str | None = None
    #: `EPIC-029` ADR D6 — the tagged owner's budget and book, `None` when
    #: no budget is registered for the tag (or the order is untagged).
    owner_budget: OwnerBudgetFacts | None = None


@dataclass(frozen=True)
class TradingLimitCheck:
    violation: TradingLimitViolation
    passed: bool


#: The thresholds the app falls back to when the configuration names none
#: (`adapter_bindings.py`). One definition, so a test double that wants "the
#: default limit" reads this instead of a copied literal (PR #303 review,
#: finding 2).
DEFAULT_TRADING_LIMITS = TradingLimits(
    max_orders_per_session=20,
    max_notional_per_order=Decimal(500),
    max_positions_per_symbol=1,
    min_order_interval=timedelta(seconds=60),
)
