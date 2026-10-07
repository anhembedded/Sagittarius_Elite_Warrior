"""`EPIC-028S` — `SessionReadyResult.account_was_read` fails closed.

@details A screen replaces its Positions and Open orders with a readiness check's
`reconciled_*` tuples only when the venue was read; empty tuples from a
skipped read would read as "flat" (the PR 309 reviews). The property is an
allow-list, and this file makes every block reason a decision: a reason added
to `SessionBlockReason` fails `test_every_block_reason_is_classified`
until it is placed on one side. The handler's tests
(`test_ensure_session_ready.py`) pin each side against the real read order.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_ready_result import (
    SessionBlockReason,
    SessionReadyResult,
)

#: Decided after `get_positions`/`get_open_orders` (`session_readiness.py`).
_READ = {
    SessionBlockReason.UNEXPECTED_POSITIONS,
    SessionBlockReason.SUPERSEDED_BY_CONCURRENT_STATE_CHANGE,
}
#: Decided before any read.
_NOT_READ = {
    SessionBlockReason.TRADING_VENUE_DISABLED,
    SessionBlockReason.CONNECTION_NOT_READY,
    SessionBlockReason.EMERGENCY_STOP_IN_PROGRESS,
}


def _refused(reason: SessionBlockReason | None) -> SessionReadyResult:
    return SessionReadyResult(
        ready=reason is None,
        block_reason=reason,
        reconciled_positions=(),
        reconciled_open_orders=(),
    )


def test_every_block_reason_is_classified() -> None:
    """Retire when: `SessionReadyResult` carries the fact itself (a field
    the handler sets) instead of deriving it from the block reason."""
    assert set(SessionBlockReason) == _READ | _NOT_READ
    assert not _READ & _NOT_READ


def test_a_success_was_read() -> None:
    assert _refused(None).account_was_read is True


@pytest.mark.parametrize("reason", sorted(_READ, key=lambda r: r.value))
def test_a_refusal_after_the_read_was_read(reason: SessionBlockReason) -> None:
    assert _refused(reason).account_was_read is True


@pytest.mark.parametrize("reason", sorted(_NOT_READ, key=lambda r: r.value))
def test_a_refusal_before_the_read_was_not(reason: SessionBlockReason) -> None:
    assert _refused(reason).account_was_read is False


def test_a_session_that_was_already_open_was_not_read() -> None:
    """Nothing was asked of the venue, so the empty tuples are not "flat"."""
    result = SessionReadyResult(
        ready=True,
        block_reason=None,
        reconciled_positions=(),
        reconciled_open_orders=(),
        already_open=True,
    )

    assert result.account_was_read is False
