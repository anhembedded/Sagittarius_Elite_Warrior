"""`EPIC-035D` — the trading clients turn a rate-limit pause into the contract error.

The call policy raises `RateLimitedApiException` so every adapter that catches a
`BinanceAPIException` keeps working. An order's submit, a cancel and an order lookup
are the calls whose caller can act on a pause (a bot halts for it), so they raise
`ExchangeRateLimitedError` — an `OrderRejectedByExchangeError` with reason
`RATE_LIMIT`, which every caller that words a rejection already words. An ordinary
refusal is unchanged.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.order_send_failure import (
    raise_for_failed_read,
    raise_for_failed_send,
    raise_rejection,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limited_api_exception import (
    RateLimitedApiException,
    rate_limited_error_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_outcome_unknown import (
    OrderOutcomeUnknownError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.exchange_answers import (
    refusal,
    timeout,
)

_PAUSE = timedelta(seconds=42)


def _pause(*, banned: bool = False) -> RateLimitedApiException:
    return RateLimitedApiException(_PAUSE, banned=banned, note="slow down")


def _order() -> Order:
    return Order(
        client_order_id=ClientOrderId("SEW-limited0001"),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal(1),
    )


def test_a_pause_becomes_the_contract_error_with_its_window_and_cause() -> None:
    cause = _pause(banned=True)

    error = rate_limited_error_of(cause)

    assert error is not None
    assert (error.retry_after, error.banned) == (_PAUSE, True)
    assert error.reason is OrderRejectionReason.RATE_LIMIT
    assert isinstance(error, OrderRejectedByExchangeError)
    assert error.__cause__ is cause


@pytest.mark.parametrize("other", [refusal(-2011), timeout(), RuntimeError("x")])
def test_anything_else_is_not_a_pause(other: BaseException) -> None:
    assert rate_limited_error_of(other) is None


def test_a_rate_limited_send_is_not_an_unknown_outcome() -> None:
    with pytest.raises(ExchangeRateLimitedError):
        raise_for_failed_send(_order(), _pause(), live=True)


def test_a_rate_limited_lookup_is_not_an_unknown_outcome_either() -> None:
    with pytest.raises(ExchangeRateLimitedError):
        raise_for_failed_read("BTCUSDT", "SEW-limited0001", _pause())


def test_a_rate_limited_cancel_names_the_pause() -> None:
    with pytest.raises(ExchangeRateLimitedError) as raised:
        raise_rejection(_pause())
    assert raised.value.retry_after == _PAUSE


def test_an_ordinary_refusal_is_the_rejection_it_always_was() -> None:
    with pytest.raises(OrderRejectedByExchangeError) as raised:
        raise_rejection(refusal(-2011, "Unknown order sent."))
    assert not isinstance(raised.value, ExchangeRateLimitedError)


def test_an_unreadable_send_is_still_an_unknown_outcome() -> None:
    with pytest.raises(OrderOutcomeUnknownError):
        raise_for_failed_send(_order(), timeout(), live=True)
