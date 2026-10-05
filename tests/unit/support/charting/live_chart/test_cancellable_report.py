"""`report_unless_cancelled` (`BUG-150`): a report to a chart closed between
the cancellation check and the emit is dropped, and only that one."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.cancellable_report import (
    report_unless_cancelled,
)
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken


def test_a_report_is_delivered_while_the_token_stands():
    received: list[str] = []

    report_unless_cancelled(CancellationToken(), received.append, "drawn")

    assert received == ["drawn"]


def test_a_cancelled_token_reports_nothing():
    token = CancellationToken()
    token.cancel()
    received: list[str] = []

    report_unless_cancelled(token, received.append, "drawn")

    assert received == []


def test_a_chart_closed_between_the_check_and_the_emit_is_dropped():
    """The race the check alone leaves open: the Qt thread cancels and
    deletes the chart after the worker checked, and the emit raises."""
    token = CancellationToken()

    def emit_on_a_chart_closed_meanwhile(_text: str) -> None:
        token.cancel()
        raise RuntimeError("Signal source has been deleted")

    report_unless_cancelled(token, emit_on_a_chart_closed_meanwhile, "drawn")


def test_a_runtime_error_the_token_does_not_explain_still_raises():
    def broken(_text: str) -> None:
        raise RuntimeError("something else")

    with pytest.raises(RuntimeError, match="something else"):
        report_unless_cancelled(CancellationToken(), broken, "drawn")
