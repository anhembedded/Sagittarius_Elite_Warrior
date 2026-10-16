"""`EPIC-039L` — a protective stop that closes the whole position, as the Algo Order API
takes it.

@details Binance's New Algo Order page (read 2026-10-16): `closePosition=true` is used with
`STOP_MARKET` or `TAKE_PROFIT_MARKET`, "cannot be used with `quantity`", "cannot be used with
`reduceOnly`"; `workingType` is `MARK_PRICE` or `CONTRACT_PRICE`. The last test pins that the
desk's own stops, which never set the new fields, are sent exactly as before."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.algo_update_parser import (
    parse_algo_update,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_algo_order_mapper import (
    map_futures_algo_payload_to_order,
    map_order_to_futures_algo_params,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.invalid_order_for_submission import (
    InvalidOrderForSubmissionError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.working_type import (
    WorkingType,
)

_METADATA = SymbolOrderMetadata(
    symbol="BTCUSDT",
    status="TRADING",
    step_size=Decimal("0.001"),
    tick_size=Decimal("0.1"),
    min_notional=Decimal(100),
    quantity_precision=3,
    price_precision=1,
    fetched_at=datetime(2026, 10, 1, tzinfo=UTC),
)
_STOP = Order(
    client_order_id=ClientOrderId("SEW-a3f9c1-0123456789"),
    symbol="BTCUSDT",
    side=OrderSide.SELL,
    order_type=OrderType.STOP_MARKET,
    quantity=Decimal(0),
    stop_price=Decimal("59000.0"),
    close_position=True,
    working_type=WorkingType.MARK_PRICE,
)


def test_a_close_position_stop_is_sent_without_quantity_and_without_reduce_only() -> (
    None
):
    params = map_order_to_futures_algo_params(_STOP, _METADATA)

    assert params == {
        "algoType": "CONDITIONAL",
        "symbol": "BTCUSDT",
        "side": "SELL",
        "positionSide": "BOTH",
        "type": "STOP_MARKET",
        "triggerPrice": "59000.0",
        "workingType": "MARK_PRICE",
        "closePosition": "true",
        "clientAlgoId": "SEW-a3f9c1-0123456789",
    }


@pytest.mark.parametrize(
    "changes",
    [{"quantity": Decimal("0.01")}, {"reduce_only": True}],
    ids=["a quantity", "reduce-only"],
)
def test_a_close_position_stop_refuses_what_the_exchange_refuses_beside_it(
    changes: dict[str, Any],
) -> None:
    with pytest.raises(InvalidOrderForSubmissionError, match="closePosition"):
        map_order_to_futures_algo_params(replace(_STOP, **changes), _METADATA)


def test_a_close_position_stop_off_the_tick_is_refused() -> None:
    with pytest.raises(InvalidOrderForSubmissionError, match="stop price"):
        map_order_to_futures_algo_params(
            replace(_STOP, stop_price=Decimal("59000.05")), _METADATA
        )


def _payload(**changes: Any) -> dict[str, Any]:
    """`GET /fapi/v1/algoOrder`'s documented answer for a close-all stop."""
    return {
        "algoId": 2146761,
        "clientAlgoId": "SEW-a3f9c1-0123456789",
        "algoType": "CONDITIONAL",
        "orderType": "STOP_MARKET",
        "symbol": "BTCUSDT",
        "side": "SELL",
        "positionSide": "BOTH",
        "algoStatus": "NEW",
        "triggerPrice": "59000.0",
        "workingType": "MARK_PRICE",
        "closePosition": True,
        "priceProtect": False,
        "reduceOnly": False,
        "createTime": 1_760_000_000_000,
        "updateTime": 1_760_000_000_000,
        **changes,
    }


def test_a_close_position_stop_is_read_back_as_one() -> None:
    order = map_futures_algo_payload_to_order(_payload())

    assert (order.close_position, order.working_type) == (True, WorkingType.MARK_PRICE)
    assert (order.order_type, order.side, order.stop_price) == (
        OrderType.STOP_MARKET,
        OrderSide.SELL,
        Decimal("59000.0"),
    )
    assert order.quantity == 0


def test_an_algo_order_that_names_no_close_position_or_working_type_is_an_ordinary_one() -> (
    None
):
    payload = _payload(quantity="0.002", closePosition=False)
    del payload["workingType"]

    order = map_futures_algo_payload_to_order(payload)

    assert (order.close_position, order.working_type) == (False, WorkingType.LAST_PRICE)
    assert order.quantity == Decimal("0.002")


def test_the_algo_update_of_a_close_position_stop_says_so() -> None:
    update = parse_algo_update(
        {
            "e": "ALGO_UPDATE",
            "T": 1_760_000_000_000,
            "o": {
                "caid": "SEW-a3f9c1-0123456789",
                "s": "BTCUSDT",
                "S": "SELL",
                "o": "STOP_MARKET",
                "q": "0",
                "X": "NEW",
                "tp": "59000.0",
                "wt": "MARK_PRICE",
                "cp": True,
                "R": False,
            },
        }
    )

    assert update.order.close_position is True
    assert update.order.working_type is WorkingType.MARK_PRICE


def test_the_desks_own_stop_is_sent_exactly_as_before() -> None:
    desk = Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        order_type=OrderType.STOP_MARKET,
        quantity=Decimal("0.002"),
        stop_price=Decimal("59000.0"),
        reduce_only=True,
    )

    assert map_order_to_futures_algo_params(desk, _METADATA) == {
        "algoType": "CONDITIONAL",
        "symbol": "BTCUSDT",
        "side": "SELL",
        "positionSide": "BOTH",
        "type": "STOP_MARKET",
        "quantity": "0.002",
        "triggerPrice": "59000.0",
        "workingType": "CONTRACT_PRICE",
        "reduceOnly": True,
        "clientAlgoId": "SEW-a91f4c72e0b8",
    }
