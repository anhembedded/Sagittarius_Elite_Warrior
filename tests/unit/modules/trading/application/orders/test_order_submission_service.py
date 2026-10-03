"""`EPIC-028O` — `OrderSubmissionService` hands every field of an
`OrderRequest` on to the query it dispatches.

@details The dispatcher is a recording double derived from the `core/` port
(`testing-rule.md` §2): it keeps what it was asked and answers with the
preview or result the port promises.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.order_submission_service import (
    OrderSubmissionService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.query import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
    InvalidClientOrderTagError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_preview import (
    OrderPreview,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_purpose import (
    OrderPurpose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    NotionalCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_PREVIEW = OrderPreview(
    order=Order(
        client_order_id=ClientOrderId("sew-1"),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.STOP_LIMIT,
        quantity=Decimal("0.01"),
        order_time=datetime(2026, 10, 1, tzinfo=UTC),
    ),
    raw_quantity=Decimal("0.01"),
    estimated_notional=Decimal(641),
    min_notional=Decimal(5),
    step_size=Decimal("0.00001"),
    notional_check=NotionalCheck.SUFFICIENT,
)


class _RecordingDispatcher(ICommandDispatcher):
    def __init__(self) -> None:
        self.dispatched: list[object] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        self.dispatched.append(input_dto)
        if isinstance(input_dto, ExecuteOrderCommand):
            return ExecuteOrderResult(None, _PREVIEW, (), None)
        return _PREVIEW


def test_a_stop_limit_request_reaches_the_query_whole() -> None:
    dispatcher = _RecordingDispatcher()
    service = OrderSubmissionService(dispatcher, TradingVenue.SPOT_TESTNET)

    service.submit(
        OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.STOP_LIMIT,
            quantity=Decimal("0.01"),
            reference_price=Decimal(64100),
            stop_price=Decimal(64050),
            time_in_force=TimeInForce.IOC,
            last_price=Decimal(64000),
        ),
        live=True,
    )

    (command,) = dispatcher.dispatched
    assert isinstance(command, ExecuteOrderCommand)
    query = command.order_request
    assert (query.stop_price, query.time_in_force, query.last_price) == (
        Decimal(64050),
        TimeInForce.IOC,
        Decimal(64000),
    )
    assert query.venue is TradingVenue.SPOT_TESTNET


def test_a_quote_sized_request_reaches_the_query_whole() -> None:
    dispatcher = _RecordingDispatcher()
    service = OrderSubmissionService(dispatcher, TradingVenue.SPOT_TESTNET)

    service.preview(
        OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal(0),
            reference_price=Decimal(64000),
            quote_quantity=Decimal(1000),
        )
    )

    (query,) = dispatcher.dispatched
    assert isinstance(query, PreviewOrderQuery)
    assert query.quote_quantity == Decimal(1000)


def test_a_protective_request_is_submitted_as_protective() -> None:
    """`EPIC-028I` — the purpose is what exempts a take-profit or stop-loss
    from the session limits; dropping it here would refuse the protection."""
    dispatcher = _RecordingDispatcher()
    service = OrderSubmissionService(dispatcher, TradingVenue.FUTURES_TESTNET)

    service.submit(
        OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.STOP_MARKET,
            quantity=Decimal("0.01"),
            reference_price=Decimal(63000),
            reduce_only=True,
            stop_price=Decimal(63000),
            last_price=Decimal(64000),
            purpose=OrderPurpose.PROTECTIVE,
        ),
        live=True,
    )

    (command,) = dispatcher.dispatched
    assert isinstance(command, ExecuteOrderCommand)
    assert command.purpose is OrderPurpose.PROTECTIVE
    assert command.order_request.reduce_only is True


def test_a_tagged_request_reaches_the_query_with_its_tag() -> None:
    """`EPIC-029A` (ADR D5): the bot tag survives the one translation."""
    dispatcher = _RecordingDispatcher()
    service = OrderSubmissionService(dispatcher, TradingVenue.SPOT_TESTNET)

    service.preview(
        OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.01"),
            reference_price=Decimal(64000),
            client_order_tag="a3f9c1",
        )
    )

    (query,) = dispatcher.dispatched
    assert isinstance(query, PreviewOrderQuery)
    assert query.client_order_tag == "a3f9c1"


def test_a_request_with_a_malformed_tag_cannot_be_built() -> None:
    with pytest.raises(InvalidClientOrderTagError):
        OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.01"),
            reference_price=Decimal(64000),
            client_order_tag="a3f9c",
        )
