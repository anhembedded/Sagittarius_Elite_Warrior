"""`EPIC-027M` — how much of one Spot asset Emergency Stop may sell.

@details The Spot analogue of a Futures `LivePosition` to close: instead of
a signed `position_amt` this app opened itself, a Spot holding is a single
non-negative quantity that may already have existed before this app ever
enabled trading (ADR: the baseline the app owns only the difference it
created). This policy answers exactly one question — given what the
account holds now and what the baseline held, how much is this app's own
surplus to sell — and answers it as a pure function so it can be
mutation-verified in isolation from `EmergencyStopCommandHandler`'s network
calls and error handling.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    OrderQuantityRoundingPolicy,
)

_ROUNDING_POLICY = OrderQuantityRoundingPolicy()


def sellable_spot_quantity(
    current_total: Decimal, baseline_quantity: Decimal, step_size: Decimal
) -> Decimal:
    """@brief The quantity of one asset Emergency Stop may sell: whatever
    the account holds now beyond what the baseline already held, floored to
    the exchange's lot step.
    @details Never negative — a holding that shrank below its own baseline
    (the user sold some by hand outside this app, or a fee was taken from
    it) has nothing left for this app to sell; `EPIC-027M`'s own acceptance
    criterion is that Emergency Stop never sells what the baseline held, so
    zero, not a negative "quantity to buy back", is the only correct answer
    here. `step_size` flooring is the same `LOT_SIZE`/`MARKET_LOT_SIZE`
    rounding every other order in this app already goes through
    (`OrderQuantityRoundingPolicy`) — a surplus smaller than one step floors
    to zero, which the caller reports as dust rather than an order.
    """
    surplus = current_total - baseline_quantity
    if surplus <= 0:
        return Decimal(0)
    return _ROUNDING_POLICY.round_quantity_down(surplus, step_size)


@dataclass(frozen=True)
class LiquidationPart:
    """One sell of an Emergency Stop liquidation: `tag` is the bot whose
    coins these are, or `None` for the surplus no bot holds."""

    tag: str | None
    quantity: Decimal


def split_liquidation(
    quantity: Decimal,
    owner_inventories: Sequence[tuple[str, Decimal]],
    step_size: Decimal,
    min_quantity: Decimal = Decimal(0),
) -> tuple[LiquidationPart, ...]:
    """@brief Splits one asset's sellable `quantity` per bot (`EPIC-029` ADR
    D6 r2): each `(tag, inventory)` takes up to its inventory, floored to
    the lot step, in the order given; only what is left beyond every bot's
    share goes out untagged.
    @details Every sell of a bot's coins carries the bot's tag, so the
    bot's inventory, derived again from its tagged orders, drops by exactly
    what was sold for it, and the user's coins are never counted as the
    bot's. Parts of zero are left out.

    A part below `min_quantity` (the exchange's minimum notional at the
    current bid) is left out too: the venue would reject it (the
    `EPIC-029A` review). It stays held as dust, and a bot's share left out
    is never folded into the untagged rest, which would sell the bot's
    coins under no tag and leave its inventory counting them.
    """
    parts: list[LiquidationPart] = []
    remaining = quantity
    for tag, inventory in owner_inventories:
        share = _ROUNDING_POLICY.round_quantity_down(
            min(inventory, remaining), step_size
        )
        remaining -= share
        if share > 0 and share >= min_quantity:
            parts.append(LiquidationPart(tag, share))
    if remaining > 0 and remaining >= min_quantity:
        parts.append(LiquidationPart(None, remaining))
    return tuple(parts)
