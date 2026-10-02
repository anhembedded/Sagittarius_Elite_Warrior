"""`BOT-144` — direct unit tests for `TradingActionsCoordinator`, the Dev
Board's per-order cancel (its other action families left in `EPIC-028M`:
Enable/Disable and Emergency Stop for `DeskSessionControls`, the manual order
for the desks' order panel behind F9).

Against the module's verified `FakeOrderSubmission`, not a bare `Mock`: a
cancel that also submitted an order is something only the fake can say.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.cancel_order_result import (
    CancelOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.coordinators.trading_actions_coordinator import (
    TradingActionsCoordinator,
)


class _Recorder:
    """A callable that remembers every call it received."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def __call__(self, *args):
        self.calls.append(args)


@pytest.fixture
def thread_manager() -> MagicMock:
    """`IThreadManager` is the shared engine kernel port; submissions are
    asserted by identity/args, never dispatched."""
    return MagicMock()


@pytest.fixture
def order_submission() -> FakeOrderSubmission:
    return FakeOrderSubmission()


@pytest.fixture
def emit_cancel_order_completed() -> _Recorder:
    return _Recorder()


@pytest.fixture
def coordinator(
    thread_manager, order_submission, emit_cancel_order_completed
) -> TradingActionsCoordinator:
    return TradingActionsCoordinator(
        thread_manager=thread_manager,
        order_submission=order_submission,
        emit_cancel_completed=emit_cancel_order_completed,
        append_log=_Recorder(),
    )


def test_request_cancel_order_submits_the_background_worker(
    coordinator, thread_manager
):
    coordinator.request_cancel_order("BTCUSDT", "abc123")

    thread_manager.submit.assert_called_once_with(
        coordinator.run_cancel_order, "BTCUSDT", "abc123"
    )


def test_run_cancel_order_cancels_exactly_that_order_and_nothing_else(
    coordinator, order_submission, emit_cancel_order_completed
):
    order_submission.cancel_answers(CancelOrderResult(None, None))

    coordinator.run_cancel_order("BTCUSDT", "abc123")

    assert order_submission.cancelled == [("BTCUSDT", "abc123")]
    # Cancelling one order must never submit one, which the port's fake can
    # say and a bare `Mock` could not.
    assert order_submission.submitted_live == []
    (call,) = emit_cancel_order_completed.calls
    symbol, client_order_id, result, error = call[0]
    assert (symbol, client_order_id) == ("BTCUSDT", "abc123")
    assert result is not None
    assert error is None


def test_run_cancel_order_reports_an_exception_rather_than_raising(
    coordinator, order_submission, emit_cancel_order_completed
):
    """`FakeOrderSubmission.cancel()` has no answer configured (its own
    unconfigured-call guard) — the coordinator must report that failure
    through the completion callback, not let it escape the worker thread."""
    coordinator.run_cancel_order("BTCUSDT", "abc123")

    (call,) = emit_cancel_order_completed.calls
    symbol, client_order_id, result, error = call[0]
    assert (symbol, client_order_id) == ("BTCUSDT", "abc123")
    assert result is None
    assert "cancel_answers" in error
