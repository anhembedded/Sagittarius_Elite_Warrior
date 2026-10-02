"""`EPIC-028S` — `EnableTradingResult.account_was_read` fails closed.

@details A screen replaces its Positions and Open orders with an enable's
`reconciled_*` tuples only when the venue was read; empty tuples from a
skipped read would read as "flat" (the PR 309 reviews). The property is an
allow-list, and this file makes every block reason a decision: a reason added
to `EnableTradingBlockReason` fails `test_every_block_reason_is_classified`
until it is placed on one side. The handler's tests
(`test_enable_trading.py`) pin each side against the real read order.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.enable_trading_result import (
    EnableTradingBlockReason,
    EnableTradingResult,
)

#: Decided after `get_positions`/`get_open_orders` (`enable_trading/handler.py`).
_READ = {
    EnableTradingBlockReason.UNEXPECTED_POSITIONS,
    EnableTradingBlockReason.SUPERSEDED_BY_CONCURRENT_STATE_CHANGE,
}
#: Decided before any read.
_NOT_READ = {
    EnableTradingBlockReason.TRADING_VENUE_DISABLED,
    EnableTradingBlockReason.CONNECTION_NOT_READY,
}


def _refused(reason: EnableTradingBlockReason | None) -> EnableTradingResult:
    return EnableTradingResult(
        enabled=reason is None,
        block_reason=reason,
        reconciled_positions=(),
        reconciled_open_orders=(),
    )


def test_every_block_reason_is_classified() -> None:
    """Retire when: `EnableTradingResult` carries the fact itself (a field
    the handler sets) instead of deriving it from the block reason."""
    assert set(EnableTradingBlockReason) == _READ | _NOT_READ
    assert not _READ & _NOT_READ


def test_a_success_was_read() -> None:
    assert _refused(None).account_was_read is True


@pytest.mark.parametrize("reason", sorted(_READ, key=lambda r: r.value))
def test_a_refusal_after_the_read_was_read(reason: EnableTradingBlockReason) -> None:
    assert _refused(reason).account_was_read is True


@pytest.mark.parametrize("reason", sorted(_NOT_READ, key=lambda r: r.value))
def test_a_refusal_before_the_read_was_not(reason: EnableTradingBlockReason) -> None:
    assert _refused(reason).account_was_read is False
