from __future__ import annotations

import json

import pytest
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.domain.trading.order_rejection_reason import (
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_error_translator import (
    translate_binance_error,
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
