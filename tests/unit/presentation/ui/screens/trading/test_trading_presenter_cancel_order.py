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

from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.cancel_order import (
    CancelOrderCommand,
    CancelOrderResult,
)


def test_cancel_order_requested_submits_background_worker(
    presenter, mock_thread_manager
):
    presenter._on_cancel_order_requested("BTCUSDT", "abc123")

    mock_thread_manager.submit.assert_called_once_with(
        presenter._run_cancel_order, "BTCUSDT", "abc123"
    )


def test_run_cancel_order_dispatches_cancel_order_command_for_exactly_that_order(
    presenter, mock_dispatcher
):
    completed = MagicMock()
    presenter.cancelOrderCompleted.connect(completed)
    mock_dispatcher.dispatch.return_value = None

    presenter._run_cancel_order("BTCUSDT", "abc123")

    mock_dispatcher.dispatch.assert_called_once_with(
        CancelOrderCommand, CancelOrderCommand("BTCUSDT", "abc123")
    )


def test_cancel_order_completed_removes_the_order_from_the_book(presenter):
    remove_spy = MagicMock()
    presenter._order_book.on_order_cancelled = remove_spy

    presenter._on_cancel_order_completed(
        ("BTCUSDT", "abc123", CancelOrderResult(None, None), None)
    )

    remove_spy.assert_called_once_with("abc123")


def test_cancel_order_completed_reports_a_dispatcher_exception(presenter):
    remove_spy = MagicMock()
    presenter._order_book.on_order_cancelled = remove_spy

    presenter._on_cancel_order_completed(("BTCUSDT", "abc123", None, "boom"))

    remove_spy.assert_not_called()
    log_entries = presenter._view_model.log_model.entries
    assert any("boom" in entry.message for entry in log_entries)
