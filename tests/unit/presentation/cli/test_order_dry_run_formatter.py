from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import ClientOrderId
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.presentation.cli.order_dry_run_formatter import (
    format_submission_accepted,
    format_submission_rejected,
    format_submission_request,
)


def _order() -> Order:
    return Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.002"),
    )


def test_request_matches_the_epics_worked_example() -> None:
    text = format_submission_request(_order())

    assert text.splitlines() == [
        "POST https://testnet.binancefuture.com/fapi/v1/order/test",
        "payload: symbol=BTCUSDT side=BUY type=MARKET quantity=0.002",
        (
            "         newClientOrderId=SEW-a91f4c72e0b8  "
            "(app tự sinh, không để thư viện sinh)"
        ),
    ]


def test_accepted_matches_the_epics_worked_example() -> None:
    assert format_submission_accepted() == (
        "Sàn CHẤP NHẬN payload.  ✔  Không có lệnh nào được tạo."
    )


def test_rejected_matches_the_epics_worked_example() -> None:
    error = OrderRejectedByExchangeError(
        OrderRejectionReason.LOT_SIZE,
        "APIError(code=-1013): Quantity less than or equal to zero.",
    )

    text = format_submission_rejected(error)

    assert text.splitlines() == [
        "Sàn TỪ CHỐI: LOT_SIZE",
        "  nguyên văn: APIError(code=-1013): Quantity less than or equal to zero.",
    ]
