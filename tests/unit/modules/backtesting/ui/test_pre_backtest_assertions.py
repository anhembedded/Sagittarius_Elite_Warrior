"""Business-facing local validation for the Backtest toolbar (BOT-095E)."""

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.pre_backtest_assertions import (
    BacktestInputField,
    PreBacktestAssertionPipeline,
    PreBacktestInput,
)


def _validate(**changes: object):
    baseline = {
        "capital_text": "10000",
        "is_custom_range": False,
        "custom_start_text": "",
        "custom_end_text": "",
    }
    baseline.update(changes)
    return PreBacktestAssertionPipeline.default().validate(PreBacktestInput(**baseline))


def test_rejects_non_numeric_capital_with_the_capital_field_targeted():
    issues = _validate(capital_text="not-a-number")

    assert len(issues) == 1
    assert issues[0].field is BacktestInputField.INITIAL_CAPITAL
    assert "Invalid" in issues[0].message


def test_rejects_non_finite_capital_instead_of_accepting_float_nan_or_inf():
    for raw_value in ("nan", "inf", "-inf"):
        issues = _validate(capital_text=raw_value)

        assert len(issues) == 1
        assert issues[0].field is BacktestInputField.INITIAL_CAPITAL


def test_rejects_non_positive_capital():
    issues = _validate(capital_text="0")

    assert issues[0].field is BacktestInputField.INITIAL_CAPITAL
    assert issues[0].message == "Initial capital must be greater than 0."


def test_accepts_a_finite_positive_capital():
    assert _validate(capital_text="10000.50") == ()


def test_rejects_an_invalid_custom_start_date_without_checking_market_metadata():
    issues = _validate(
        is_custom_range=True,
        custom_start_text="2026/08/17",
        custom_end_text="2026-08-18 00:00",
    )

    assert issues[0].field is BacktestInputField.CUSTOM_START
    assert "format" in issues[0].message


def test_rejects_a_custom_range_whose_end_is_not_after_its_start():
    issues = _validate(
        is_custom_range=True,
        custom_start_text="2026-08-17 10:00",
        custom_end_text="2026-08-17 10:00",
    )

    assert issues[0].field is BacktestInputField.CUSTOM_END
    assert issues[0].message == "Start date must be before end date."


def test_empty_custom_end_remains_an_unbounded_range_not_a_false_validation_error():
    assert (
        _validate(
            is_custom_range=True,
            custom_start_text="2026-08-17 10:00",
            custom_end_text="",
        )
        == ()
    )


# --------------------------------------------------------------------- #
# `BUG-109` — Realtime/tick mode + a *bounded* but very wide range (the
# "365 ngày qua" preset, or any custom range picked that wide) reaches
# an `IRangeCoverage` probe at the tick interval with no progress bar
# and no cancellation (`BUG-073`'s own root cause, never fixed at the SQL
# layer) — a real session hung for minutes with nothing on screen. The old
# `is_unbounded_range`-only check never caught this: start_time is real,
# not None. `_validate()`'s baseline never sets `is_tick_mode`, so every
# test above this point is unaffected by the new check.
# --------------------------------------------------------------------- #

_TICK_MODE_LIMIT_DAYS = 7


def test_tick_mode_with_an_unbounded_range_is_still_rejected():
    """Locks the pre-existing `BUG-073` behavior — untested until now."""
    issues = _validate(is_tick_mode=True, is_unbounded_range=True)

    assert len(issues) == 1
    assert issues[0].field is BacktestInputField.TIME_RANGE_PRESET


def test_tick_mode_with_a_range_at_the_limit_is_accepted():
    end = datetime(2026, 9, 8, tzinfo=UTC)
    start = end - timedelta(days=_TICK_MODE_LIMIT_DAYS)

    assert _validate(is_tick_mode=True, start_time=start, end_time=end) == ()


def test_tick_mode_with_a_bounded_range_wider_than_the_limit_is_rejected():
    """The actual reported hang: a *bounded* 365-day range (e.g. the "365
    ngày qua" preset) in tick mode — not `is_unbounded_range`, a real
    `start_time`/`end_time` pair that is simply too wide."""
    end = datetime(2026, 9, 1, 23, 59, tzinfo=UTC)
    start = end - timedelta(days=364)

    issues = _validate(is_tick_mode=True, start_time=start, end_time=end)

    assert len(issues) == 1
    assert issues[0].field is BacktestInputField.TIME_RANGE_PRESET
    assert str(_TICK_MODE_LIMIT_DAYS) in issues[0].message


def test_a_wide_range_outside_tick_mode_is_not_rejected():
    """Pins the guard to tick mode only — `BAR_CLOSE` mode at a coarse
    timeframe stays cheap even over a wide range (same scoping `BUG-073`'s
    own fix pinned for the unbounded case)."""
    end = datetime(2026, 9, 1, tzinfo=UTC)
    start = end - timedelta(days=364)

    assert _validate(is_tick_mode=False, start_time=start, end_time=end) == ()


def test_tick_mode_with_only_a_start_time_resolved_is_not_yet_rejected():
    """A transient toolbar state mid-resolution (`end_time` not settled
    yet) must not false-reject — same reasoning `is_unbounded_range`
    already applied to a still-resolving state."""
    assert (
        _validate(is_tick_mode=True, start_time=datetime(2020, 1, 1, tzinfo=UTC)) == ()
    )
