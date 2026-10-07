"""BUG-170 — an emergency stop never states an unconfirmed close as fact.

A close whose answer was a `502` page may be done. The stop asks the exchange
for it by the client order id; when that read fails too it says the close may be
done, goes on to the next position, and never claims "still open".
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock

from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop.command import (
    EmergencyStopCommand,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.session.emergency_stop_builders import (
    make_handler,
    position_payload,
)

_PAGE = "<html><head><title>502 Bad Gateway</title></head></html>"


def _page() -> BinanceAPIException:
    return BinanceAPIException(SimpleNamespace(text=_PAGE), 502, _PAGE)


def _no_such_order() -> BinanceAPIException:
    return BinanceAPIException(
        None, 400, json.dumps({"code": -2013, "msg": "Order does not exist."})
    )


def _raw(*, read_back: Exception) -> Mock:
    raw = Mock()
    raw.futures_get_open_orders.return_value = []
    raw.futures_get_open_algo_orders.return_value = []
    raw.futures_position_information.return_value = [
        position_payload("BTCUSDT"),
        position_payload("BTCUSDT", amt="0.003"),
    ]
    raw.futures_create_order.side_effect = [_page(), {}]
    raw.futures_get_order.side_effect = read_back
    raw.futures_get_algo_order.side_effect = read_back
    return raw


def test_an_unconfirmed_close_is_said_to_be_possibly_done_and_the_rest_go_on() -> None:
    raw = _raw(read_back=_page())

    result = make_handler(raw_client=raw).execute(
        EmergencyStopCommand(venue=TradingVenue.FUTURES_TESTNET)
    )

    detail = result.positions_closed.detail
    assert result.positions_closed.succeeded is False
    assert raw.futures_create_order.call_count == 2, "the next position still closes"
    assert "BTCUSDT" in detail and "may be done" in detail
    assert "still open" not in detail
    assert "<" not in detail


def test_a_close_the_exchange_does_not_hold_is_reported_as_an_error() -> None:
    raw = _raw(read_back=_no_such_order())

    result = make_handler(raw_client=raw).execute(
        EmergencyStopCommand(venue=TradingVenue.FUTURES_TESTNET)
    )

    assert result.positions_closed.succeeded is False
    assert "0/2" in result.positions_closed.detail
    assert "BTCUSDT" in result.positions_closed.detail
