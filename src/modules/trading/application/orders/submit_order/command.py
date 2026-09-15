from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.query import (
    PreviewOrderQuery,
)


@dataclass(frozen=True)
class SubmitOrderCommand:
    """@brief Normalize one order and send it to the venue's *test* endpoint.

    `EPIC-021F`. The name is historical and the docstring is where it stops
    being misleading: nothing is ever created by this command. The
    `ITradingClient` bound for it runs in `OrderSubmissionMode.VALIDATE_ONLY`,
    so the request goes to `POST /fapi/v1/order/test`, which checks signature,
    key permissions and payload and creates no order. `EPIC-025` PR 1.3c-2
    moved it out of the legacy tree into `trading`, where every other order
    use case already lives, and published it as
    `IOrderSubmission.validate()`.

    @details Wraps a `PreviewOrderQuery` rather than repeating its fields:
    submitting an order and previewing one build the exact same normalized
    `Order` (rounding, notional estimate) — the only difference is what
    happens *after* that, so there is exactly one place that "how do we
    turn a symbol/side/qty/price into an `Order`" logic lives.
    """

    order_request: PreviewOrderQuery
