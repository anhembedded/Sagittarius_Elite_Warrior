from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.application.use_cases.queries.preview_order.query import (
    PreviewOrderQuery,
)


@dataclass(frozen=True)
class SubmitOrderCommand:
    """@brief Command to normalize and submit one order (`EPIC-021F`).

    @details Wraps a `PreviewOrderQuery` rather than repeating its fields:
    submitting an order and previewing one build the exact same normalized
    `Order` (rounding, notional estimate) — the only difference is what
    happens *after* that, so there is exactly one place that "how do we
    turn a symbol/side/qty/price into an `Order`" logic lives.
    """

    order_request: PreviewOrderQuery
