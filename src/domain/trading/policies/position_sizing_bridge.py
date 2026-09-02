"""`EPIC-021G` — turns a real account balance into a live order quantity,
reusing backtesting's own `PositionSizing`/`MarginRiskPolicy` rather than
inventing a second sizing model live trading would have to keep in sync
with the backtested one by hand.

@details `MarginRiskPolicy.calculate_margin_and_notional()` (`BOT-104`)
already implements every `PositionSizingType` — this module is only the
glue: `Decimal` (this app's real balance) in, `Decimal` (a step-rounded
quantity) out, `float` in between because that policy's own contract is
`float` throughout (a backtest-scoped policy this bridge reuses as-is,
not a reason to fork it). `side` never changes the *magnitude*
`calculate_margin_and_notional` returns — it only appears in that
policy's own log line — so a fixed `PositionSide.LONG` is passed through
regardless of which direction this order actually is.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.domain.backtesting.policies.margin_risk_policy import (
    MarginRiskPolicy,
)
from Sagittarius_Elite_Warrior.src.domain.policies.order_quantity_rounding_policy import (
    OrderQuantityRoundingPolicy,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_sizing import (
    PositionSizing,
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
    produce a valid allocation (same "return zero, never raise" contract
    `MarginRiskPolicy` itself uses) — the caller treats a zero quantity as
    nothing to send, not as an error.
    """
    if reference_price <= 0:
        return Decimal(0)

    margin_risk_policy = MarginRiskPolicy()
    _, notional_capital = margin_risk_policy.calculate_margin_and_notional(
        side=PositionSide.LONG,
        effective_price=float(reference_price),
        current_equity=float(available_balance),
        available_balance=float(available_balance),
        sizing=sizing,
        leverage=leverage,
        stop_loss_pct=stop_loss_pct,
    )
    if notional_capital <= 0:
        return Decimal(0)

    raw_quantity = Decimal(str(notional_capital)) / reference_price
    return OrderQuantityRoundingPolicy().round_quantity_down(raw_quantity, step_size)
