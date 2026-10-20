from __future__ import annotations

import json

import pytest
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.binance_error_translator import (
    translate_binance_error,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectionReason,
)


def _exception(code: int, message: str) -> BinanceAPIException:
    return BinanceAPIException(None, 400, json.dumps({"code": code, "msg": message}))


@pytest.mark.parametrize(
    ("code", "message", "expected"),
    [
        # This epic's own worked example (`EPIC-021F` §5).
        (-1013, "Quantity less than or equal to zero.", OrderRejectionReason.LOT_SIZE),
        (-1013, "Filter failure: PRICE_FILTER", OrderRejectionReason.PRICE_FILTER),
        (
            -1013,
            "Filter failure: MIN_NOTIONAL, notional too small",
            OrderRejectionReason.MIN_NOTIONAL,
        ),
        (-2019, "Margin is insufficient.", OrderRejectionReason.INSUFFICIENT_MARGIN),
        (
            -4164,
            "Order's notional must be no smaller than 100.",
            OrderRejectionReason.MIN_NOTIONAL,
        ),
        (
            -2022,
            "ReduceOnly Order is rejected.",
            OrderRejectionReason.REDUCE_ONLY_REJECTED,
        ),
        (-1003, "Too many requests.", OrderRejectionReason.RATE_LIMIT),
        # `BUG-099` — four more realistic live-order codes, previously
        # falling through to `UNKNOWN`.
        (-1015, "Too many new orders.", OrderRejectionReason.RATE_LIMIT),
        (
            -1111,
            "Precision is over the maximum defined for this asset.",
            OrderRejectionReason.LOT_SIZE,
        ),
        (
            -4003,
            "Quantity less than or equal to zero.",
            OrderRejectionReason.LOT_SIZE,
        ),
        (
            -2027,
            "Exceeded the maximum allowable position at current leverage.",
            OrderRejectionReason.INSUFFICIENT_MARGIN,
        ),
        (
            -4131,
            "The counterparty's best price does not meet the PERCENT_PRICE filter limit.",
            OrderRejectionReason.PRICE_FILTER,
        ),
        # `EPIC-035E` — the symbol's status and a delisting. The texts are
        # from Binance's documentation, not re-verified against a live call
        # (egress to the exchange is blocked in this sandbox).
        (-1013, "Market is closed.", OrderRejectionReason.SYMBOL_NOT_TRADING),
        (-1013, "Symbol is not trading.", OrderRejectionReason.SYMBOL_NOT_TRADING),
        (-1121, "Invalid symbol.", OrderRejectionReason.SYMBOL_NOT_LISTED),
        # `EPIC-035F` — the three codes `connection_failure` files under
        # `KEY_REJECTED` for the connection check are the same refusal on an order.
        (
            -2015,
            "Invalid API-key, IP, or permissions for action.",
            OrderRejectionReason.KEY_REJECTED,
        ),
        (-2008, "Invalid Api-Key ID.", OrderRejectionReason.KEY_REJECTED),
        (-2014, "API-key format invalid.", OrderRejectionReason.KEY_REJECTED),
        # `BUG-236` — the USDⓈ-M order-filter family (error-code page read 2026-10-20),
        # which read as `UNKNOWN`: price and stop price, quantity, the mark-price caps.
        (-4001, "Price less than 0.", OrderRejectionReason.PRICE_FILTER),
        (-4002, "Price greater than max price.", OrderRejectionReason.PRICE_FILTER),
        (-4004, "Quantity less than min quantity.", OrderRejectionReason.LOT_SIZE),
        (-4005, "Quantity greater than max quantity.", OrderRejectionReason.LOT_SIZE),
        (-4006, "Stop price less than zero.", OrderRejectionReason.PRICE_FILTER),
        (
            -4007,
            "Stop price greater than max price.",
            OrderRejectionReason.PRICE_FILTER,
        ),
        (-4013, "Price less than min price.", OrderRejectionReason.PRICE_FILTER),
        (-4014, "Price not increased by tick size.", OrderRejectionReason.PRICE_FILTER),
        (
            -4016,
            "Price is higher than mark price multiplier cap.",
            OrderRejectionReason.PRICE_FILTER,
        ),
        (-4023, "Qty not increased by step size.", OrderRejectionReason.LOT_SIZE),
        (
            -4024,
            "Price is lower than mark price multiplier floor.",
            OrderRejectionReason.PRICE_FILTER,
        ),
        (
            -4183,
            "Price is higher than stop price multiplier cap.",
            OrderRejectionReason.PRICE_FILTER,
        ),
        (
            -4184,
            "Price is lower than stop price multiplier floor.",
            OrderRejectionReason.PRICE_FILTER,
        ),
        (
            -4210,
            "Stop price is higher than price multiplier cap.",
            OrderRejectionReason.PRICE_FILTER,
        ),
        (
            -4211,
            "Stop price is lower than price multiplier floor.",
            OrderRejectionReason.PRICE_FILTER,
        ),
    ],
)
def test_real_binance_codes_map_to_the_expected_reason(
    code: int, message: str, expected: OrderRejectionReason
) -> None:
    assert translate_binance_error(_exception(code, message)) is expected


def test_clock_skew_code_falls_through_to_unknown() -> None:
    """`-1021` is a real, documented Binance code — already classified for
    the *connection* check by `EPIC-021D`'s `ConnectionFailureKind.
    CLOCK_SKEW` — but no `OrderRejectionReason` member describes it, so it
    must not be silently forced into one."""
    assert (
        translate_binance_error(_exception(-1021, "Timestamp for this request..."))
        is OrderRejectionReason.UNKNOWN
    )


def test_unrecognized_code_falls_through_to_unknown() -> None:
    assert (
        translate_binance_error(_exception(-9999, "Some new error."))
        is OrderRejectionReason.UNKNOWN
    )


def test_dash_1013_with_unrecognized_text_falls_through_to_unknown() -> None:
    assert (
        translate_binance_error(_exception(-1013, "Something unexpected happened."))
        is OrderRejectionReason.UNKNOWN
    )


def test_minus_2010_has_a_named_reason() -> None:
    """`EPIC-035T` — Spot's "new order rejected": the exchange read the order and
    refused it for its own content, which a bot survives rung by rung."""
    reason = translate_binance_error(
        _exception(-2010, "Account has insufficient balance for requested action.")
    )

    assert reason is OrderRejectionReason.NEW_ORDER_REJECTED


def test_an_order_the_exchange_does_not_hold_has_a_named_reason() -> None:
    """A cancel or a read of an order that already filled or ended: `-2011` ("Unknown order
    sent.") and `-2013` ("Order does not exist.") are the same fact."""
    for code, message in (
        (-2011, "Unknown order sent."),
        (-2013, "Order does not exist."),
    ):
        assert (
            translate_binance_error(_exception(code, message))
            is OrderRejectionReason.UNKNOWN_ORDER
        )


@pytest.mark.parametrize(
    "code",
    [-4008, -4009, -4010, -4011, -4012, -4017, -4018, -4025, -4029, -4030, -4058],
)
def test_a_symbol_configuration_error_is_not_an_order_filter_refusal(code: int) -> None:
    """`BUG-236` — the family's other codes say the exchange's own symbol table is
    wrong (a tick below zero, a maximum under the minimum): nothing the order's
    numbers can fix, so they stay `UNKNOWN` with their text."""
    assert (
        translate_binance_error(_exception(code, "A symbol configuration error."))
        is OrderRejectionReason.UNKNOWN
    )
