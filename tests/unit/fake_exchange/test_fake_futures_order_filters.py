"""`EPIC-037E` — the fake Futures exchange refuses what Binance refuses: an order off the
symbol's tick or step, under its minimum notional, past its size limits, or of the wrong
position side. Each rule's source is in `futures_order_filters.py` / `futures_order_checks.py`.

@details Boundary-value cases: each limit is tried at the value and one unit either side.
`BTCUSDT` in the fake: tick `0.10`, step and minimum quantity `0.001`, maximum `1000`, minimum
notional `100`, maximum price `4529764`, 2 price decimals, 3 quantity decimals.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests" / "sanity"))
from fake_exchange.futures_listing import FUTURES_EXCHANGE_INFO
from fake_exchange.order_book_state import OrderBookState
from Sagittarius_Elite_Warrior.tests.unit.fake_exchange.futures_world import (
    SYMBOL,
    market,
    order_params,
)


def _refusal_code(state: OrderBookState, params: dict[str, str]) -> int | None:
    status, body = state.place(params)
    return None if status == 200 else int(body["code"])  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("price", "code"),
    [
        ("63000.0", None),
        ("63000.1", None),
        ("63000.05", -4014),
        ("63000.123", -1111),
        ("556.7", -1013),
        ("556.8", None),
        ("4529764.0", -2027),  # past the filter; the leverage ceiling refuses it
        ("4529764.1", -1013),
    ],
    ids=lambda value: str(value),
)
def test_a_price_off_the_tick_or_outside_the_band_is_refused(
    price: str, code: int | None
) -> None:
    state = OrderBookState()

    assert _refusal_code(state, order_params("BUY", price, "0.5")) == code


@pytest.mark.parametrize(
    ("quantity", "code"),
    [
        (
            "0.001",
            -4164,
        ),  # at the step and the minimum quantity, 64 USDT: under the notional
        ("0.002", None),  # 126 USDT
        ("0.0025", -1111),
        ("0", -4003),
        ("-1", -4003),
        ("1000", -2027),  # past the filter; the leverage ceiling refuses it
        ("1000.001", -4005),
    ],
    ids=lambda value: str(value),
)
def test_a_quantity_off_the_step_or_outside_the_limits_is_refused(
    quantity: str, code: int | None
) -> None:
    state = OrderBookState()

    assert _refusal_code(state, order_params("BUY", "63000.0", quantity)) == code


@pytest.mark.parametrize(
    ("price", "quantity", "code"),
    [("625.0", "0.160", None), ("625.0", "0.159", -4164), ("624.9", "0.160", -4164)],
    ids=["at 100", "quantity under", "price under"],
)
def test_the_minimum_notional_is_a_boundary_of_price_times_quantity(
    price: str, quantity: str, code: int | None
) -> None:
    state = OrderBookState()

    assert _refusal_code(state, order_params("BUY", price, quantity)) == code


def test_a_market_order_is_judged_at_the_book_price() -> None:
    state = OrderBookState()

    assert (
        _refusal_code(state, order_params("BUY", "0", "0.001", order_type="MARKET"))
        == -4164
    )
    assert (
        _refusal_code(state, order_params("BUY", "0", "0.002", order_type="MARKET"))
        is None
    )


def test_a_reduce_only_order_is_exempt_from_the_minimum_notional() -> None:
    state = OrderBookState()
    market(state, "BUY", "0.002")

    closing = order_params("SELL", "64000.0", "0.001", reduce_only=True)

    assert _refusal_code(state, closing) is None


def test_a_position_side_that_is_not_the_accounts_mode_is_refused() -> None:
    state = OrderBookState()
    hedge_order = {**order_params("BUY", "63000.0", "0.5"), "positionSide": "LONG"}

    assert _refusal_code(state, hedge_order) == -4061

    assert state.set_position_mode({"dualSidePosition": "true"})[0] == 200
    assert _refusal_code(state, order_params("BUY", "63000.0", "0.5")) == -4061
    assert _refusal_code(state, hedge_order) is None


def test_a_refused_order_is_remembered_nowhere() -> None:
    state = OrderBookState()

    assert _refusal_code(state, order_params("BUY", "63000.05", "0.5")) == -4014

    assert state.open_orders(SYMBOL) == []
    assert state.drain_user_data_events() == []


def test_every_listed_symbol_enforces_the_tick_it_advertises() -> None:
    """`BUG-147` / `CS-007`: a tick in `exchangeInfo` the order route ignored."""
    state = OrderBookState()
    assert FUTURES_EXCHANGE_INFO["symbols"], "the listing is empty"
    for row in FUTURES_EXCHANGE_INFO["symbols"]:
        price_filter = next(
            f for f in row["filters"] if f["filterType"] == "PRICE_FILTER"
        )
        tick = Decimal(price_filter["tickSize"])
        precision = int(row["pricePrecision"])
        off_tick = Decimal(price_filter["minPrice"]) * 2 + tick / 2
        on_tick = Decimal(price_filter["minPrice"]) * 2
        step = next(f for f in row["filters"] if f["filterType"] == "LOT_SIZE")[
            "stepSize"
        ]
        quantity = str(Decimal(step) * 100_000)
        base = {**order_params("BUY", "0", quantity), "symbol": row["symbol"]}
        refused = _refusal_code(
            state, {**base, "price": f"{off_tick:.{precision + 1}f}"}
        )
        assert refused in {-4014, -1111}, row["symbol"]
        assert (
            _refusal_code(state, {**base, "price": f"{on_tick:.{precision}f}"}) is None
        ), row["symbol"]
