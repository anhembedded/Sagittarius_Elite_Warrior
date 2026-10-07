"""BUG-170 — a live order whose answer was unreadable is resolved by asking the exchange for it.

The handler runs over the real Futures client with a session double that
answers the submit with a `502` page. It then reads the order by its client
order id and reports what is true: placed (an ordinary result), not placed, or
still unknown. A session counter is spent whenever the order may be live.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_outcome_unknown import (
    OrderNotPlacedError,
    OrderOutcomeUnknownError,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.orders.execute_order_builders import (
    make_handler,
    order_request,
)

_PAGE = "<html><head><title>502 Bad Gateway</title></head><body>nginx</body></html>"


def _html_answer() -> BinanceAPIException:
    return BinanceAPIException(SimpleNamespace(text=_PAGE), 502, _PAGE)


def _json_error(code: int, message: str) -> BinanceAPIException:
    return BinanceAPIException(None, 400, json.dumps({"code": code, "msg": message}))


def _live() -> ExecuteOrderCommand:
    return ExecuteOrderCommand(order_request=order_request(), live=True)


def _order_row(client_order_id: str) -> dict[str, str]:
    return {
        "clientOrderId": client_order_id,
        "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "MARKET",
        "origQty": "0.002",
        "status": "FILLED",
    }


def _raw_with_unreadable_submit() -> Mock:
    raw = Mock()
    raw.futures_create_order.side_effect = _html_answer()
    return raw


def test_an_order_the_exchange_holds_is_reported_placed() -> None:
    raw = _raw_with_unreadable_submit()
    raw.futures_get_order.side_effect = lambda **p: _order_row(p["origClientOrderId"])
    handler, state = make_handler(raw_client=raw)

    result = handler.execute(_live())

    assert result.blocked_by is None
    assert result.submitted_order is not None
    assert result.submitted_order.client_order_id.startswith("SEW-")
    assert state.orders_sent_this_session == 1


def test_an_order_the_exchange_does_not_hold_is_reported_not_placed() -> None:
    raw = _raw_with_unreadable_submit()
    raw.futures_get_order.side_effect = _json_error(-2013, "Order does not exist.")
    raw.futures_get_algo_order.side_effect = _json_error(-2013, "Order does not exist.")
    handler, state = make_handler(raw_client=raw)

    with pytest.raises(OrderNotPlacedError) as refusal:
        handler.execute(_live())

    assert refusal.value.client_order_id.startswith("SEW-")
    assert state.orders_sent_this_session == 0
    assert "BTCUSDT" not in state.known_open_symbols


def test_an_order_that_cannot_be_asked_about_is_still_unknown_and_counted() -> None:
    raw = _raw_with_unreadable_submit()
    raw.futures_get_order.side_effect = _html_answer()
    handler, state = make_handler(raw_client=raw)

    with pytest.raises(OrderOutcomeUnknownError) as unknown:
        handler.execute(_live())

    assert unknown.value.client_order_id.startswith("SEW-")
    assert "<" not in str(unknown.value)
    # It may be live: it counts against the session's limits and the symbol.
    assert state.orders_sent_this_session == 1
    assert "BTCUSDT" in state.known_open_symbols


def test_the_read_asks_for_the_id_the_submission_carried() -> None:
    raw = _raw_with_unreadable_submit()
    raw.futures_get_order.side_effect = _json_error(-2013, "Order does not exist.")
    raw.futures_get_algo_order.side_effect = _json_error(-2013, "Order does not exist.")
    handler, _ = make_handler(raw_client=raw)

    with pytest.raises(OrderNotPlacedError):
        handler.execute(_live())

    sent = raw.futures_create_order.call_args.kwargs["newClientOrderId"]
    assert raw.futures_get_order.call_args.kwargs["origClientOrderId"] == sent
