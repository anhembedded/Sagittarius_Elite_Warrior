"""`EPIC-028J` — a position is closed by a reduce-only market order for its
whole size on the opposite side."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.position_close_order import (
    market_close_order_for,
)


def _position(amount: str) -> LivePosition:
    return LivePosition(
        symbol="BTCUSDT",
        position_amt=Decimal(amount),
        entry_price=Decimal(60000),
        mark_price=Decimal("60123.4"),
        unrealized_pnl=Decimal(1),
        leverage=10,
        margin_type=MarginType.CROSSED,
        liquidation_price=None,
        updated_at=datetime(2026, 10, 1, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("amount", "side"),
    [("0.025", OrderSide.SELL), ("-0.025", OrderSide.BUY)],
)
def test_the_whole_position_is_closed_on_the_opposite_side(
    amount: str, side: OrderSide
) -> None:
    request = market_close_order_for(_position(amount))

    assert request.side is side
    assert request.quantity == Decimal("0.025")
    assert request.order_type is OrderType.MARKET
    assert request.reduce_only is True
    assert request.symbol == "BTCUSDT"
    assert request.reference_price == Decimal("60123.4")
