from __future__ import annotations

import json
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.application.use_cases.queries.preview_order.order_preview import (
    OrderPreview,
)
from Sagittarius_Elite_Warrior.src.domain.policies.order_quantity_rounding_policy import (
    NotionalCheck,
)
from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.presentation.cli.order_preview_formatter import (
    format_order_preview,
    order_preview_to_dict,
)


def _ready_preview() -> OrderPreview:
    order = Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.013"),
    )
    return OrderPreview(
        order=order,
        raw_quantity=Decimal("0.0137"),
        estimated_notional=Decimal("832.00"),
        min_notional=Decimal(100),
        step_size=Decimal("0.001"),
        notional_check=NotionalCheck.SUFFICIENT,
    )


def _rejected_preview() -> OrderPreview:
    order = Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.001"),
    )
    return OrderPreview(
        order=order,
        raw_quantity=Decimal("0.001"),
        estimated_notional=Decimal("64.00"),
        min_notional=Decimal(100),
        step_size=Decimal("0.001"),
        notional_check=NotionalCheck.INSUFFICIENT,
    )


def test_ready_preview_matches_the_epics_worked_example() -> None:
    text = format_order_preview(_ready_preview())

    assert "client_order_id : SEW-a91f4c72e0b8" in text
    assert "BTCUSDT / BUY   position_side=BOTH (One-way)" in text
    assert "MARKET / 0.013  (làm tròn xuống từ 0.0137, step 0.001)" in text
    assert "832.00 USDT     ≥ minNotional 100.00 ✔" in text
    assert text.splitlines()[-1] == (
        "Trạng thái: SẴN SÀNG GỬI  (chưa gửi — task này không có đường ra mạng)"
    )


def test_rejected_preview_matches_the_epics_worked_example() -> None:
    text = format_order_preview(_rejected_preview())

    assert text.splitlines()[-1] == (
        "Trạng thái: TỪ CHỐI  MIN_NOTIONAL — 64.00 USDT < 100.00 USDT"
    )


def test_quantity_line_omits_rounding_note_when_nothing_was_rounded() -> None:
    order = Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.013"),
    )
    preview = OrderPreview(
        order=order,
        raw_quantity=Decimal("0.013"),
        estimated_notional=Decimal("832.00"),
        min_notional=Decimal(100),
        step_size=Decimal("0.001"),
        notional_check=NotionalCheck.SUFFICIENT,
    )

    text = format_order_preview(preview)

    assert "làm tròn" not in text


def test_json_export_round_trips_the_domain_order() -> None:
    payload = order_preview_to_dict(_ready_preview())
    serialized = json.dumps(payload, ensure_ascii=False)
    parsed = json.loads(serialized)

    assert parsed["order"]["client_order_id"] == "SEW-a91f4c72e0b8"
    assert parsed["order"]["symbol"] == "BTCUSDT"
    assert parsed["order"]["side"] == "BUY"
    assert parsed["order"]["order_type"] == "market"
    assert parsed["order"]["quantity"] == "0.013"
    assert parsed["order"]["status"] == "new"
    assert parsed["order"]["price"] is None
    assert parsed["notional_check"] == "sufficient"
