"""Renders the outcome of one `order-dry-run` attempt as the text
`EPIC-021F` §5 specifies.

@details `EPIC-021F` only ever submits `OrderSubmissionMode.VALIDATE_ONLY`
— this module intentionally does not import `OrderSubmissionMode` or
branch on it: the epic's own guard requires `grep -rn
"OrderSubmissionMode.LIVE" src/` to show zero call sites until
`EPIC-021G` opens it, so nothing here spells that name out even in a
currently-unreachable branch. Extending this for a `LIVE`-mode entry
point is `EPIC-021G`'s job, alongside lifting the guard itself.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.order_rejection_reason import (
    OrderRejectedByExchangeError,
)

#: `TradingVenue` has no `MAINNET` member (ADR §3), so this is the one host
#: this app's trading path ever talks to.
_VALIDATE_ONLY_URL = "https://testnet.binancefuture.com/fapi/v1/order/test"


def format_submission_request(order: Order) -> str:
    lines = [
        f"POST {_VALIDATE_ONLY_URL}",
        (
            f"payload: symbol={order.symbol} side={order.side.value} "
            f"type={order.order_type.name} quantity={order.quantity}"
        ),
        (
            f"         newClientOrderId={order.client_order_id}  "
            "(app tự sinh, không để thư viện sinh)"
        ),
    ]
    return "\n".join(lines)


def format_submission_accepted() -> str:
    return "Sàn CHẤP NHẬN payload.  ✔  Không có lệnh nào được tạo."


def format_submission_rejected(error: OrderRejectedByExchangeError) -> str:
    return "\n".join(
        [
            f"Sàn TỪ CHỐI: {error.reason.name}",
            f"  nguyên văn: {error.raw_message}",
        ]
    )
