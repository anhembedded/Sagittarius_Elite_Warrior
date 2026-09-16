"""`EPIC-021G` — turns a real account balance into a live order quantity.

@details `ISizingPolicy` answers in capital (`EPIC-025` PR 2.1d); an exchange
takes quantities, rounded to the symbol's lot filter. This is that one step,
and it is the whole reason a "bridge" exists at all: `Decimal` (this app's real
balance) in, `Decimal` (a step-rounded quantity) out, `float` in between
because the sizing rule's own contract is `float` throughout.

The rounding is `trading`'s own published policy, not arithmetic retyped here —
which is also exactly the division of labour ADR D17 draws: `strategy` decides
how much capital to commit, `trading` owns what the exchange will accept. The
submit path rounds again, against the same `step_size` from the same
`IMarketMetadataProvider`; rounding down twice is the same answer, and doing it
here too is what lets `LiveTradingCoordinator` tell the operator *"sizing
produced nothing to send"* (`BUG-084`) instead of letting a sub-lot quantity
travel on to be refused for a different reason.

@par Where `side` went
It used to be here, fixed at `PositionSide.LONG` "regardless of which direction
this order actually is", because the sizing rule took one and never used it for
anything but a word in a log line. `ISizingPolicy` does not take one, so there
is nothing to pass.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.vo.position_sizing import PositionSizing
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.policies.margin_sizing_policy import (
    MarginSizingPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    OrderQuantityRoundingPolicy,
)


def calculate_live_order_quantity(
    sizing: PositionSizing,
    available_balance: Decimal,
    reference_price: Decimal,
    leverage: float,
    step_size: Decimal,
    stop_loss_pct: float | None = None,
) -> Decimal:
    """@brief Computes the order quantity `sizing` implies against
    `available_balance`, rounded down to `step_size`.
    @return `Decimal(0)` if `sizing`/`leverage`/`reference_price` cannot
    produce a valid allocation (the same "return zero, never raise" contract
    `ISizingPolicy` itself promises) — the caller treats a zero quantity as
    nothing to send, not as an error.
    """
    if reference_price <= 0:
        return Decimal(0)

    allocation = MarginSizingPolicy().allocate(
        sizing=sizing,
        effective_price=float(reference_price),
        current_equity=float(available_balance),
        available_balance=float(available_balance),
        leverage=leverage,
        stop_loss_pct=stop_loss_pct,
    )
    # Load-bearing for a *second* implementation rather than for this one:
    # `MarginSizingPolicy` already answers `NO_ALLOCATION` here, so dividing its
    # zero notional would reach `Decimal(0)` anyway. What this refuses is a
    # negative notional, which `is_fundable` calls unfundable and which would
    # otherwise become a negative order quantity — and ADR D17's promise to the
    # user is precisely that a different sizing rule (ATR-based, Kelly) can be
    # dropped in behind this port.
    if not allocation.is_fundable:
        return Decimal(0)

    raw_quantity = Decimal(str(allocation.notional_capital)) / reference_price
    return OrderQuantityRoundingPolicy().round_quantity_down(raw_quantity, step_size)
