"""`EPIC-012G` — the timeframe fallback must recover, not raise.

@details The branch these tests cover was broken from `e071c8d` (2026-08-22)
until this task: `except ValueError: tf = TimeFrame.M1`, naming an enum member
that does not exist. Reaching the recovery path raised `AttributeError` — the
handler replaced a recoverable error with an unrecoverable one. Nothing caught
it because no test ever entered the branch.
"""

from __future__ import annotations

import logging

import pytest
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.timeframe_parsing import (
    FALLBACK_TIMEFRAME,
    timeframe_or_fallback,
)


@pytest.mark.parametrize(
    "raw",
    ["1m", "5m", "15m", "1h", "1d", "1M"],
)
def test_a_valid_timeframe_is_returned_unchanged(raw: str) -> None:
    """Every value the toolbar can produce must survive the parse untouched.

    @details `"1M"` (one month) and `"1m"` (one minute) differ only in case
    and both exist, so a fallback that lower-cased its input would silently
    turn a monthly backtest into a minute one.
    """
    assert timeframe_or_fallback(raw) == TimeFrame(raw)


@pytest.mark.parametrize("raw", ["", "M1", "1minute", "7m", "NONE"])
def test_an_unusable_timeframe_falls_back_instead_of_raising(raw: str) -> None:
    """The whole point of the branch: recover, do not replace one error with
    another. `"M1"` is included because it is what the broken code named."""
    assert timeframe_or_fallback(raw) is FALLBACK_TIMEFRAME


def test_the_fallback_is_a_real_member_of_the_enum() -> None:
    """Guards the exact defect: `TimeFrame.M1` was not a member at all, so
    the recovery branch raised `AttributeError` the moment it ran."""
    assert FALLBACK_TIMEFRAME in set(TimeFrame)


def test_falling_back_warns_because_it_means_the_state_is_broken(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A value that reaches here and does not parse is not a normal input —
    no picker can produce one. `logging-rule.md` §2: log the branch that
    degraded, with the reason."""
    with caplog.at_level(logging.WARNING, logger="App.BacktestTimeframe"):
        timeframe_or_fallback("M1")

    assert any(
        record.levelno == logging.WARNING and "M1" in record.getMessage()
        for record in caplog.records
    )


def test_a_valid_timeframe_does_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    """The counterpart, so the warning stays evidence of something wrong."""
    with caplog.at_level(logging.WARNING, logger="App.BacktestTimeframe"):
        timeframe_or_fallback("5m")

    assert caplog.records == []
