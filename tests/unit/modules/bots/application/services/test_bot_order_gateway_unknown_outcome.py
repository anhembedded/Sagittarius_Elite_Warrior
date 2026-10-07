"""BUG-170 — a bot's order whose outcome is unknown carries its client order id.

The id lets the stop sequence mark the order off the ladder, so a fill that
arrives later for an exit slice is not booked as a ladder level's fill.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_order_gateway import (
    BotIdentity,
    BotOrderGateway,
    OrderOutcomeKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_outcome_unknown import (
    OrderNotPlacedError,
    OrderOutcomeUnknownError,
)

_ID = "SEW-abc123-0123456789"


def _gateway(failure: Exception) -> BotOrderGateway:
    ports = Mock()
    ports.order_submission.submit.side_effect = failure
    return BotOrderGateway(
        ports, BotIdentity("bot:abc123", "abc123", "BTCUSDT"), Mock()
    )


def test_an_unknown_outcome_is_a_fault_that_names_the_order() -> None:
    outcome = _gateway(
        OrderOutcomeUnknownError("BTCUSDT", _ID, "HTTP 502")
    ).market_sell(Decimal("0.01"), Decimal(100))

    assert outcome.kind is OrderOutcomeKind.FAULT
    assert outcome.client_order_id == _ID
    assert "may be live" in outcome.detail


def test_a_not_placed_order_is_a_fault_with_no_order_to_track() -> None:
    outcome = _gateway(OrderNotPlacedError("BTCUSDT", _ID, "HTTP 502")).market_sell(
        Decimal("0.01"), Decimal(100)
    )

    assert outcome.kind is OrderOutcomeKind.FAULT
    assert outcome.client_order_id == ""
    assert "not placed" in outcome.detail
