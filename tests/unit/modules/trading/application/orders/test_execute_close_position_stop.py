"""`EPIC-039L` — a bot's protective stop (`closePosition`) through preview and execute.

@details The handler is `execute_order_builders.py`'s: the real `ExecuteOrderCommandHandler`
over the real `FuturesTradingClient`, its raw session a `Mock`. What the exchange is sent is
read from that session, because it is the wire that Binance's New Algo Order page constrains:
`closePosition` beside neither `quantity` nor `reduceOnly`."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_purpose import (
    OrderPurpose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    NotionalCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.working_type import (
    WorkingType,
)

from .execute_order_builders import make_handler, order_request

_MARK = Decimal(64000)


def _stop(**overrides: object) -> PreviewOrderQuery:
    """A long's protective stop: a sell stop-market below the mark that closes the lot."""
    fields: dict[str, object] = {
        "side": OrderSide.SELL,
        "order_type": OrderType.STOP_MARKET,
        "quantity": Decimal(0),
        "reference_price": _MARK,
        "stop_price": Decimal(60000),
        "last_price": _MARK,
        "close_position": True,
        "working_type": WorkingType.MARK_PRICE,
    }
    return order_request(**(fields | overrides))


def _protective(request: PreviewOrderQuery) -> ExecuteOrderCommand:
    return ExecuteOrderCommand(
        order_request=request, live=True, purpose=OrderPurpose.PROTECTIVE
    )


def test_the_exchange_is_sent_a_close_position_stop_on_the_mark_without_a_quantity() -> (
    None
):
    raw_client = Mock()
    handler, _ = make_handler(raw_client=raw_client)

    result = handler.execute(_protective(_stop()))

    assert result.blocked_by is None
    params = raw_client.futures_create_algo_order.call_args.kwargs
    assert params["closePosition"] == "true"
    assert params["workingType"] == "MARK_PRICE"
    assert params["type"] == "STOP_MARKET"
    assert "quantity" not in params
    assert "reduceOnly" not in params


def test_a_close_position_stop_has_no_quantity_for_the_minimum_notional_to_refuse() -> (
    None
):
    """A stop with nothing to size would always fall under the exchange's minimum
    notional, which is for orders that trade a quantity."""
    handler, _ = make_handler(raw_client=Mock())

    result = handler.execute(_protective(_stop()))

    assert result.preview is not None
    assert result.preview.notional_check is NotionalCheck.SUFFICIENT
    assert result.preview.order.close_position is True
    assert result.preview.order.quantity == 0


def test_a_close_position_stop_is_not_counted_as_a_trade() -> None:
    state = TradingSessionState()
    state.enable(set())
    handler, _ = make_handler(raw_client=Mock(), session_state=state)

    handler.execute(_protective(_stop()))

    assert state.orders_sent_this_session == 0
    assert state.time_since_last_order("BTCUSDT", datetime.now(UTC)) is None


def test_a_stop_above_the_market_for_a_long_is_refused_before_the_network() -> None:
    raw_client = Mock()
    handler, _ = make_handler(raw_client=raw_client)

    result = handler.execute(_protective(_stop(stop_price=Decimal(65000))))

    assert result.blocked_by is not None
    raw_client.futures_create_algo_order.assert_not_called()


def test_a_close_position_order_cannot_be_an_entry() -> None:
    with pytest.raises(ValueError, match="only reduces"):
        ExecuteOrderCommand(order_request=_stop(), live=True)


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"quantity": Decimal("0.002")}, "no quantity"),
        ({"reduce_only": True}, "reduce-only"),
        (
            {
                "order_type": OrderType.LIMIT,
                "stop_price": None,
                "last_price": None,
            },
            "stop-market",
        ),
    ],
    ids=["a quantity", "reduce-only", "a limit order"],
)
def test_a_close_position_order_the_exchange_would_refuse_never_builds(
    changes: dict[str, object], match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        _stop(**changes)
