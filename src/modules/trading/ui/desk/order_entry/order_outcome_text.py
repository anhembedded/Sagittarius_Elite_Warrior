"""`EPIC-028H` — what the order panel says about a previewed or submitted
order, without Qt: why a preview cannot be confirmed, and what a submit
ended as. Moved out of `OrderEntryPresenter` by `EPIC-028I` (the presenter
outgrew 400 lines); unchanged.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_preview import (
    OrderPreview,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    NotionalCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.stop_price_check import (
    StopPriceCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.execute_order_block_reason import (
    format_execute_order_block_reason,
)


def preview_refusal(preview: OrderPreview, limit: Decimal | None) -> str | None:
    if preview.stop_check is StopPriceCheck.WRONG_SIDE:
        return (
            "The stop price has already been crossed; the order would trigger at once."
        )
    # A quote-sized buy's quantity is only an estimate; the exchange
    # sizes it from the quote, so only its notional is checked.
    if preview.order.quote_quantity is None and preview.order.quantity <= 0:
        return f"The amount is below one lot of {preview.step_size}."
    if preview.notional_check is NotionalCheck.INSUFFICIENT:
        return (
            "The order is worth less than the symbol's minimum of "
            f"{preview.min_notional}."
        )
    # The panel judged the order at the tick-rounded price too; this is
    # the gate's own figure, so a confirmation never offers what
    # `ExecuteOrderCommandHandler`'s limit refuses.
    if limit is not None and preview.estimated_notional > limit:
        return (
            f"The order is worth {preview.estimated_notional}, more than the "
            f"app's limit of {limit} per order."
        )
    return None


def result_text(result: ExecuteOrderResult) -> tuple[str, bool]:
    if result.blocked:
        return format_execute_order_block_reason(result.blocked_by), False
    order = result.submitted_order
    if order is None:
        return "The order was not sent.", False
    return f"Order placed ({order.client_order_id}).", True
