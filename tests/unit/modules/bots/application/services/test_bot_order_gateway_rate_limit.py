"""`EPIC-035D` — a rate limit reaches the bot as a value with its pause, not as a fault.

The gateway is where an exception from trading becomes a named outcome for the
lifecycle. A rate limit (the exchange's, or the venue's gate closed after another
call's) is its own outcome, `RATE_LIMITED`, carrying the pause: it is neither a
refusal of the order nor a request that may have reached the exchange (an order
the gate stopped was never sent), so it must not become `FAULT`.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_order_gateway import (
    BotIdentity,
    BotOrderGateway,
    OrderOutcomeKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

_PAUSE = timedelta(seconds=75)


def _limited() -> ExchangeRateLimitedError:
    return ExchangeRateLimitedError(_PAUSE, banned=False, raw_message="slow down")


def _gateway(*, submit: Exception | None = None, cancel: Exception | None = None):
    ports = Mock()
    ports.order_submission.submit.side_effect = submit
    ports.order_submission.cancel.side_effect = cancel
    return BotOrderGateway(
        ports, BotIdentity("bot:abc123", "abc123", "BTCUSDT"), Mock()
    )


def test_a_rate_limited_submit_is_rate_limited_with_its_pause_not_a_fault() -> None:
    outcome = _gateway(submit=_limited()).place_limit(
        OrderSide.BUY, Decimal(100), Decimal(1)
    )

    assert outcome.kind is OrderOutcomeKind.RATE_LIMITED
    assert outcome.retry_after == _PAUSE
    assert not outcome.done


def test_a_rate_limited_market_order_is_rate_limited_too() -> None:
    gateway = _gateway(submit=_limited())

    assert (
        gateway.market_sell(Decimal(1), Decimal(100)).kind
        is OrderOutcomeKind.RATE_LIMITED
    )
    assert (
        gateway.market_buy(Decimal(100), Decimal(100)).kind
        is OrderOutcomeKind.RATE_LIMITED
    )


def test_a_rate_limited_cancel_is_rate_limited_with_its_pause() -> None:
    outcome = _gateway(cancel=_limited()).cancel("SEW-abc")

    assert outcome.kind is OrderOutcomeKind.RATE_LIMITED
    assert outcome.retry_after == _PAUSE
    assert outcome.client_order_id == "SEW-abc"


def test_a_rate_limit_that_was_seen_is_taken_once() -> None:
    gateway = _gateway(submit=_limited())
    gateway.place_limit(OrderSide.BUY, Decimal(100), Decimal(1))

    assert gateway.take_rate_limit() == _PAUSE
    assert gateway.take_rate_limit() is None


def test_a_plain_fault_is_still_a_fault() -> None:
    outcome = _gateway(submit=RuntimeError("boom")).place_limit(
        OrderSide.BUY, Decimal(100), Decimal(1)
    )
    assert outcome.kind is OrderOutcomeKind.FAULT
