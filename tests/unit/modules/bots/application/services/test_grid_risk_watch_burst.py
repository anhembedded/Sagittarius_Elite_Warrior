"""`BUG-218` - a burst of position reports keeps one re-read pending; it never starves and never repeats.

@details Each fill of the owner's 2026-10-15 burst reported a new pair of figures (the account's
report and the order's arrive in either order on testnet), and the log held ~20
`re-reading in 5 s` lines in 12 s. A re-read registers the budget again, which is what costs
weight, so there is one at a time: a newer report moves it, to at most `MAX_RECHECK_DELAYS` delays
after the first.
"""

from __future__ import annotations

import logging
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    PositionDivergence,
    PositionDivergenceKind,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.test_grid_risk_watch import (
    SYMBOL,
    _advance,
    _Rig,
)

D = Decimal


def _reported(figure: int) -> PositionDivergence:
    """A divergence with figures of its own: what each fill of a burst reports."""
    return PositionDivergence(
        PositionDivergenceKind.POSITION_CHANGED_UNORDERED,
        "bot",
        "tag",
        SYMBOL,
        D("0.5") + D(figure) / 10,
        D(0),
    )


def test_a_run_of_reports_keeps_one_re_read_pending_and_never_starves_it() -> None:
    """`BUG-218`: every fill of a burst reported a new pair of figures, and the owner's log
    held ~20 `re-reading in 5 s` lines in 12 s. One re-read is pending: a newer report moves
    it, to at most three delays after the first, so a stream that never goes quiet is still
    read (a real foreign position must not hide behind a busy account)."""
    rig = _Rig()
    rig.exchange.still_diverged = None

    for second in range(16):
        rig.world.executor.facts.on_position_divergence(_reported(second))
        rig.beat()
        _advance(rig, 1)

    assert rig.exchange.rechecks == 1, "moved past the first delay, read by the third"


def test_a_burst_that_goes_quiet_is_read_once_after_its_last_report() -> None:
    rig = _Rig()
    rig.exchange.still_diverged = None

    for second in range(4):
        rig.world.executor.facts.on_position_divergence(_reported(second))
        _advance(rig, 1)
        rig.beat()
    assert rig.exchange.rechecks == 0, "the first report's five seconds passed: moved"
    _advance(rig, 5)
    rig.beat()

    assert rig.exchange.rechecks == 1


def test_only_the_first_report_of_a_pending_re_read_is_told_at_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="App.Bots.GridExecutor")
    rig = _Rig()

    for second in range(5):
        rig.world.executor.facts.on_position_divergence(_reported(second))

    told = [r for r in caplog.records if "re-reading in" in r.getMessage()]
    assert [r.levelno for r in told] == [logging.INFO] + [logging.DEBUG] * 4
