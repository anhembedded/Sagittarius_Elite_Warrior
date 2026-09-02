"""Renders `OrderPreview` as the text `EPIC-021E` §5 specifies — a
normalized-order block plus a ready/rejected status line — or as the
underlying domain object for `--json`. Shared by every entry point that
previews an order, so they never drift."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.application.use_cases.queries.preview_order.order_preview import (
    OrderPreview,
)
from Sagittarius_Elite_Warrior.src.domain.policies.order_quantity_rounding_policy import (
    NotionalCheck,
)


def _quantity_line(preview: OrderPreview) -> str:
    order = preview.order
    if preview.raw_quantity == order.quantity:
        return f"{order.order_type.name} / {order.quantity}"
    return (
        f"{order.order_type.name} / {order.quantity}  "
        f"(làm tròn xuống từ {preview.raw_quantity}, step {preview.step_size})"
    )


def format_order_preview(preview: OrderPreview) -> str:
    order = preview.order
    is_sufficient = preview.notional_check is NotionalCheck.SUFFICIENT
    comparator = "≥" if is_sufficient else "<"
    mark = "✔" if is_sufficient else "✘"

    lines = [
        "Order đã chuẩn hoá",
        f"  client_order_id : {order.client_order_id}",
        (
            f"  symbol/side     : {order.symbol} / {order.side.value}   "
            "position_side=BOTH (One-way)"
        ),
        f"  type/quantity   : {_quantity_line(preview)}",
        (
            f"  notional ước tính: {preview.estimated_notional:,.2f} USDT     "
            f"{comparator} minNotional {preview.min_notional:,.2f} {mark}"
        ),
    ]

    if is_sufficient:
        lines.append(
            "Trạng thái: SẴN SÀNG GỬI  (chưa gửi — task này không có đường ra mạng)"
        )
    else:
        lines.append(
            "Trạng thái: TỪ CHỐI  MIN_NOTIONAL — "
            f"{preview.estimated_notional:,.2f} USDT < {preview.min_notional:,.2f} USDT"
        )

    return "\n".join(lines)


def order_preview_to_dict(preview: OrderPreview) -> dict[str, object]:
    """@brief The domain `Order` (plus the rounding decision around it) as
    a plain, JSON-serializable dict — for `--json` to diff by eye against
    the request payload `EPIC-021F`'s adapter will eventually build."""
    order = preview.order
    return {
        "order": {
            "client_order_id": str(order.client_order_id),
            "symbol": order.symbol,
            "side": order.side.value,
            "order_type": order.order_type.value,
            "quantity": str(order.quantity),
            "status": order.status.value,
            "price": str(order.price) if order.price is not None else None,
            "stop_price": (
                str(order.stop_price) if order.stop_price is not None else None
            ),
            "time_in_force": (
                order.time_in_force.value if order.time_in_force is not None else None
            ),
            "reduce_only": order.reduce_only,
        },
        "raw_quantity": str(preview.raw_quantity),
        "estimated_notional": str(preview.estimated_notional),
        "min_notional": str(preview.min_notional),
        "step_size": str(preview.step_size),
        "notional_check": preview.notional_check.value,
    }
