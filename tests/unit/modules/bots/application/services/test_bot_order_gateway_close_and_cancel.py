"""A bot's close is sent as a close, and a cancel of an order the exchange no longer holds is gone, not a fault.

The stop of a Futures bot closes its position with reduce-only market orders. Sent as ordinary
entries they were counted among the bot's open orders by the owner budget, so a stop whose
cancelled orders the exchange still listed was refused its own close (`owner_budget_open_orders`)
and halted with the position open. And a cancel that met an order the exchange no longer holds
(`-2011`) became a fault that ended the stop in ERROR, although the order was gone, which is what
the cancel wanted.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_order_gateway import (
    BotIdentity,
    BotOrderGateway,
    OrderOutcomeKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_purpose import (
    OrderPurpose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)

_ID = "SEW-abc123-0123456789"


def _gateway(submission: FakeOrderSubmission) -> BotOrderGateway:
    ports = Mock()
    ports.order_submission = submission
    return BotOrderGateway(
        ports, BotIdentity("bot:abc123", "abc123", "BTCUSDT"), Mock()
    )


def test_a_reduce_only_market_close_is_sent_for_the_close_purpose() -> None:
    submission = FakeOrderSubmission()
    submission.submit_answers(ExecuteOrderResult(None, None, (), None))

    _gateway(submission).market_reduce_only(
        OrderSide.SELL, Decimal("0.01"), Decimal(100)
    )

    (request,) = submission.submitted_live
    assert request.reduce_only
    assert request.purpose is OrderPurpose.CLOSE


def test_a_ladder_limit_order_is_still_an_entry() -> None:
    submission = FakeOrderSubmission()
    submission.submit_answers(ExecuteOrderResult(None, None, (), None))

    _gateway(submission).place_limit(
        OrderSide.SELL, Decimal(100), Decimal("0.01"), reduce_only=True
    )

    (request,) = submission.submitted_live
    assert request.purpose is OrderPurpose.ENTRY


def test_a_cancel_of_an_order_the_exchange_does_not_hold_is_gone_not_a_fault() -> None:
    submission = FakeOrderSubmission()
    submission.cancel_raises(
        OrderRejectedByExchangeError(
            OrderRejectionReason.UNKNOWN_ORDER, "Unknown order sent."
        )
    )

    outcome = _gateway(submission).cancel(_ID)

    assert outcome.kind is OrderOutcomeKind.GONE
    assert not outcome.done
    assert outcome.client_order_id == _ID


@pytest.mark.parametrize(
    "reason", [OrderRejectionReason.UNKNOWN, OrderRejectionReason.REDUCE_ONLY_REJECTED]
)
def test_any_other_refusal_of_a_cancel_stays_a_fault(
    reason: OrderRejectionReason,
) -> None:
    submission = FakeOrderSubmission()
    submission.cancel_raises(OrderRejectedByExchangeError(reason, "refused"))

    assert _gateway(submission).cancel(_ID).kind is OrderOutcomeKind.FAULT
