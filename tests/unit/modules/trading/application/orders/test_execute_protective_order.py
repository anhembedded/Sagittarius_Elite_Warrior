"""`EPIC-028I` — a protective order (a reduce-only take-profit or
stop-loss) and a close pass the app's trading limits and are not counted as
trades, and an order that claims either purpose but could open a position
(not reduce-only, on Spot, or a protective order that does not wait for a
trigger) is refused before it reaches the handler.

@details The handler is `test_execute_order.py`'s: the real
`ExecuteOrderCommandHandler` over the real `FuturesTradingClient`, its raw
session a `Mock`."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_purpose import (
    OrderPurpose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.stop_price_check import (
    StopPriceCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimitViolation,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .test_execute_order import _handler, _order_request

_LAST = Decimal(64000)


def _stop_loss(**overrides: object) -> ExecuteOrderCommand:
    """A long's stop-loss: a reduce-only sell stop-market below the last
    price, worth far more than the 500 USDT per-order limit."""
    fields: dict[str, object] = {
        "side": OrderSide.SELL,
        "order_type": OrderType.STOP_MARKET,
        "quantity": Decimal("0.5"),
        "reference_price": Decimal(63000),
        "stop_price": Decimal(63000),
        "last_price": _LAST,
        "reduce_only": True,
    }
    request = _order_request(**(fields | overrides))
    return ExecuteOrderCommand(
        order_request=request, live=True, purpose=OrderPurpose.PROTECTIVE
    )


def _exhausted_session() -> TradingSessionState:
    """A session at its order cap, with an order on the symbol a moment ago
    and a position already open on it."""
    state = TradingSessionState()
    state.enable({"BTCUSDT"})
    now = datetime.now(UTC)
    for _ in range(20):
        state.record_order_sent("BTCUSDT", now)
    return state


def test_a_protective_order_passes_every_limit_and_is_sent() -> None:
    raw_client = Mock()
    state = _exhausted_session()
    handler, _ = _handler(raw_client=raw_client, session_state=state)

    result = handler.execute(_stop_loss())

    assert result.blocked_by is None
    assert all(check.passed for check in result.limit_checks)
    params = raw_client.futures_create_algo_order.call_args.kwargs
    assert (params["type"], params["side"], params["reduceOnly"]) == (
        "STOP_MARKET",
        "SELL",
        True,
    )


def test_the_same_order_as_an_entry_is_refused_by_the_limits() -> None:
    """The exemption is the purpose, not the order: the same stop-market
    sent as an entry meets every limit it breaks."""
    state = _exhausted_session()
    handler, _ = _handler(raw_client=Mock(), session_state=state)
    entry = _stop_loss()
    command = ExecuteOrderCommand(order_request=entry.order_request, live=True)

    result = handler.execute(command)

    assert result.blocked_by is TradingLimitViolation.MAX_ORDERS_PER_SESSION


def test_a_protective_order_is_not_counted_as_a_trade() -> None:
    state = TradingSessionState()
    state.enable(set())
    handler, _ = _handler(raw_client=Mock(), session_state=state)

    handler.execute(_stop_loss())

    assert state.orders_sent_this_session == 0
    assert state.time_since_last_order("BTCUSDT", datetime.now(UTC)) is None


@pytest.mark.parametrize("purpose", [OrderPurpose.PROTECTIVE, OrderPurpose.CLOSE])
def test_an_order_that_passes_the_limits_must_be_reduce_only(
    purpose: OrderPurpose,
) -> None:
    with pytest.raises(ValueError, match="must be reduce-only"):
        ExecuteOrderCommand(order_request=_order_request(), purpose=purpose)


@pytest.mark.parametrize(
    ("purpose", "order_type", "stop_price"),
    [
        (OrderPurpose.PROTECTIVE, OrderType.STOP_MARKET, Decimal(63000)),
        (OrderPurpose.CLOSE, OrderType.MARKET, None),
    ],
)
def test_spot_gets_no_exemption_because_it_ignores_reduce_only(
    purpose: OrderPurpose, order_type: OrderType, stop_price: Decimal | None
) -> None:
    """The PR #307 review: the Spot mapper never sends `reduceOnly`, so a
    "reduce-only" Spot buy of any size would pass every limit."""
    request = _order_request(
        order_type=order_type,
        reduce_only=True,
        stop_price=stop_price,
        last_price=_LAST,
        venue=TradingVenue.SPOT_TESTNET,
    )
    with pytest.raises(ValueError, match="enforces reduce-only"):
        ExecuteOrderCommand(order_request=request, live=True, purpose=purpose)


def test_a_protective_order_must_wait_for_a_trigger() -> None:
    with pytest.raises(ValueError, match="triggered type"):
        _stop_loss(order_type=OrderType.MARKET, stop_price=None)


def test_a_close_passes_every_limit_and_is_not_counted() -> None:
    """The PR #307 review: a close sent as an entry could never close a
    position larger than the per-order notional, nor any position in a
    session at its order cap."""
    raw_client = Mock()
    state = _exhausted_session()
    handler, _ = _handler(raw_client=raw_client, session_state=state)
    request = _order_request(
        side=OrderSide.SELL, quantity=Decimal("0.5"), reduce_only=True
    )

    result = handler.execute(
        ExecuteOrderCommand(
            order_request=request, live=True, purpose=OrderPurpose.CLOSE
        )
    )

    assert result.blocked_by is None
    assert all(check.passed for check in result.limit_checks)
    assert state.orders_sent_this_session == 20
    params = raw_client.futures_create_order.call_args.kwargs
    assert (params["type"], params["side"], params["reduceOnly"]) == (
        "MARKET",
        "SELL",
        True,
    )


def test_a_stop_loss_the_market_already_crossed_is_never_sent() -> None:
    raw_client = Mock()
    handler, _ = _handler(raw_client=raw_client)

    result = handler.execute(
        _stop_loss(stop_price=Decimal(64500), reference_price=Decimal(64500))
    )

    assert result.preview is not None
    assert result.preview.stop_check is StopPriceCheck.WRONG_SIDE
    raw_client.futures_create_algo_order.assert_not_called()


def test_a_take_profit_waits_on_the_other_side_of_the_market() -> None:
    """A long's take-profit is a sell above the last price; the stop rule
    would call it crossed."""
    raw_client = Mock()
    handler, _ = _handler(raw_client=raw_client)

    result = handler.execute(
        _stop_loss(
            order_type=OrderType.TAKE_PROFIT_MARKET,
            stop_price=Decimal(66000),
            reference_price=Decimal(66000),
        )
    )

    assert result.blocked_by is None
    assert result.preview is not None
    assert result.preview.stop_check is StopPriceCheck.ON_TRIGGER_SIDE
    params = raw_client.futures_create_algo_order.call_args.kwargs
    assert (params["type"], params["triggerPrice"]) == (
        "TAKE_PROFIT_MARKET",
        "66000",
    )
