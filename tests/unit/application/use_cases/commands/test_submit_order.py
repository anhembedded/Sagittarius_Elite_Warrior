from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.use_cases.commands.submit_order import (
    SubmitOrderCommand,
    SubmitOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.preview_order import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide


def test_execute_submits_the_preview_handlers_normalized_order() -> None:
    """`SubmitOrderCommandHandler` reuses `PreviewOrderQueryHandler` as a
    plain collaborator (not through the dispatcher) so normalization can
    never drift between `order-preview` and `order-dry-run`."""
    order_request = PreviewOrderQuery(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.002"),
        reference_price=Decimal(64000),
    )
    normalized_order = Mock()
    preview = Mock(order=normalized_order)
    preview_handler = Mock()
    preview_handler.execute.return_value = preview
    trading_client = Mock()
    trading_client.place_order.return_value = normalized_order
    handler = SubmitOrderCommandHandler(preview_handler, trading_client)

    result = handler.execute(SubmitOrderCommand(order_request=order_request))

    preview_handler.execute.assert_called_once_with(order_request)
    trading_client.place_order.assert_called_once_with(normalized_order)
    assert result is normalized_order
