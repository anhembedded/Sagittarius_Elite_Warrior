"""`EPIC-024B` §0 — per-order cancel on the Trading screen's Open Orders
table, the mirror-image of `test_dashboard_presenter.py`'s identical
tests: `OpenOrdersTable`/`OpenOrdersPanel` are one shared component
(`EPIC-023A`), so the "Huỷ" button reaches both screens and both
Presenters must wire it for real.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.cancel_order_result import (
    CancelOrderResult,
)


def test_cancel_order_requested_submits_background_worker(
    presenter, mock_thread_manager
):
    presenter._on_cancel_order_requested("BTCUSDT", "abc123")

    mock_thread_manager.submit.assert_called_once_with(
        presenter._run_cancel_order, "BTCUSDT", "abc123"
    )


def test_run_cancel_order_cancels_exactly_that_order_and_nothing_else(
    presenter, order_submission
):
    completed = MagicMock()
    presenter.cancelOrderCompleted.connect(completed)
    order_submission.cancel_answers(CancelOrderResult(None, None))

    presenter._run_cancel_order("BTCUSDT", "abc123")

    assert order_submission.cancelled == [("BTCUSDT", "abc123")]
    # Cancelling must never have submitted anything, which the fake can say
    # and a mocked dispatcher could not.
    assert order_submission.submitted_live == []


def test_cancel_order_completed_removes_the_order_from_the_book(presenter):
    remove_spy = MagicMock()
    presenter._order_book.on_order_cancelled = remove_spy

    presenter._on_cancel_order_completed(
        ("BTCUSDT", "abc123", CancelOrderResult(None, None), None)
    )

    remove_spy.assert_called_once_with("abc123")


def test_cancel_order_completed_reports_a_failure_from_the_port(presenter):
    remove_spy = MagicMock()
    presenter._order_book.on_order_cancelled = remove_spy

    presenter._on_cancel_order_completed(("BTCUSDT", "abc123", None, "boom"))

    remove_spy.assert_not_called()
    log_entries = presenter._view_model.log_model.entries
    assert any("boom" in entry.message for entry in log_entries)
