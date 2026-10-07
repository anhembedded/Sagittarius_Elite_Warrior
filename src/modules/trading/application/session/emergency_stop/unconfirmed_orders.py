"""`BUG-170` — what the emergency stop builds and says around an order it could not confirm.

A close or a sale whose answer was unreadable, and whose read-back failed too,
may be live: the result says so instead of counting it open or closed.
"""

from __future__ import annotations

from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.emergency_stop_result import (
    EmergencyStopStepResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)


def closing_order_for(position: LivePosition) -> Order:
    """The reduce-only market order that closes `position`."""
    side = OrderSide.SELL if position.side is PositionSide.LONG else OrderSide.BUY
    return Order(
        client_order_id=generate_client_order_id(),
        symbol=position.symbol,
        side=side,
        order_type=OrderType.MARKET,
        quantity=abs(position.position_amt),
        reduce_only=True,
    )


def unconfirmed_close(
    closed: int, total: int, symbols: Sequence[str]
) -> EmergencyStopStepResult:
    """Some closes got no readable answer: they may be done, the rest went on."""
    return EmergencyStopStepResult(
        False,
        f"Closed {closed}/{total} positions. The exchange gave no readable answer "
        f"for {', '.join(symbols)}: the close may be done. Check Positions.",
    )


def unconfirmed_sale(asset: str) -> EmergencyStopStepResult:
    """A sale got no readable answer: it may be live, so it is not sent again."""
    return EmergencyStopStepResult(
        False,
        f"The sale of {asset} got no readable answer and may be live; it was not "
        "sent again. Check Open orders and balances.",
    )
