"""BUG-170 — the strategy's live order that got no readable answer is never logged as rejected.

Its own file: `test_live_trading_coordinator.py` is over the god-file ceiling.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_outcome_unknown import (
    OrderNotPlacedError,
    OrderOutcomeUnknownError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.strategy.application.services.test_live_trading_coordinator import (
    _coordinator,
    _signal,
)


def test_an_unknown_outcome_is_an_error_saying_the_order_may_be_live(caplog) -> None:
    submission = FakeOrderSubmission()
    submission.submit_raises(
        OrderOutcomeUnknownError("BTCUSDT", "SEW-a91f4c72e0b8", "HTTP 502")
    )

    with caplog.at_level(logging.WARNING):
        _coordinator(submission).handle(_signal())  # must not raise

    (record,) = [r for r in caplog.records if "SEW-a91f4c72e0b8" in r.getMessage()]
    assert record.levelno == logging.ERROR
    assert "may be live" in record.getMessage()
    assert "rejected" not in record.getMessage().lower()


def test_a_not_placed_order_is_a_warning_that_is_not_a_rejection(caplog) -> None:
    submission = FakeOrderSubmission()
    submission.submit_raises(
        OrderNotPlacedError("BTCUSDT", "SEW-a91f4c72e0b8", "HTTP 502")
    )

    with caplog.at_level(logging.WARNING):
        _coordinator(submission).handle(_signal())  # must not raise

    (record,) = [r for r in caplog.records if "SEW-a91f4c72e0b8" in r.getMessage()]
    assert record.levelno == logging.WARNING
    assert "not placed" in record.getMessage()
    assert "rejected" not in record.getMessage().lower()
