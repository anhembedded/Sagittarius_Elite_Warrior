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
