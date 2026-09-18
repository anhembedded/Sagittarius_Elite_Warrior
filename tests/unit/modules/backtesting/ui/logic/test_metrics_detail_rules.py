"""`metrics_detail_rules` — the extended-metrics readout, with no dialog.

## Restated from a suite the gate never ran

`MetricsDetailVM` had 12 tests at
`src/presentation/ui/qml/MetricsDetailPanel/tests/` — under `src/`, which the
gate's `pytest tests` does not collect. `CS-004` again, and this is the third
suite this phase has had to rewrite here rather than move.

Eleven of the twelve are restated below: the grouping, the ungrouped card
falling into OTHER rather than vanishing, each verdict bucket, the drawdown
duration reading the run's real timeframe, the bar including a gross loss
stored negative, and the footer. The twelfth — that `requestCopy`/`requestClose`
emit their signals — went with the `QObject` that had them; the dialog's own
Copy and Close buttons are covered in `test_metrics_detail_dialog.py`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.metrics_detail_rules import (
    build_clipboard_text,
    build_footer,
    build_gross_bar,
    build_groups,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.performance_metrics_view import (
    StatCardData,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Tone

_NEUTRAL = Tone.NEUTRAL
_ONE_HOUR = 3600


def _card(title: str, value: str, suffix: str = "") -> StatCardData:
    return StatCardData(title, value, _NEUTRAL, suffix, "", _NEUTRAL)


def _row(groups, title: str):
    return next(row for group in groups for row in group.rows if row.title == title)


def test_cards_are_split_into_their_sections_in_a_fixed_order():
    groups = build_groups(
        [
            _card("Max Consecutive Wins", "4"),
            _card("Sharpe Ratio", "1.5"),
            _card("Gross Profit", "100"),
        ],
        timeframe_seconds=60,
    )

    assert [group.label for group in groups] == ["PROFIT & LOSS", "RISK", "STREAKS"]


def test_an_empty_section_is_dropped_rather_than_shown_with_nothing_under_it():
    groups = build_groups([_card("Gross Profit", "100")], timeframe_seconds=60)

    assert [group.label for group in groups] == ["PROFIT & LOSS"]


def test_a_card_no_section_claims_falls_into_other_rather_than_vanishing():
    """Total Fees Paid and the in/out-of-sample figures are not in the design's
    four sections, and losing them would be worse than showing them last."""
    groups = build_groups([_card("Total Fees Paid", "12.5")], timeframe_seconds=60)

    assert [group.label for group in groups] == ["OTHER"]
    assert _row(groups, "TOTAL FEES PAID").value == "12.5"


def test_a_negative_sharpe_marks_both_the_figure_and_its_verdict():
    """The design colours "-63.24" itself red, not only its pill — so the
    verdict's tone is written onto the value as well as the badge."""
    groups = build_groups([_card("Sharpe Ratio", "-63.24")], timeframe_seconds=60)
    row = _row(groups, "SHARPE RATIO")

    assert row.badge_text == "Very Poor"
    assert row.badge_tone is Tone.NEGATIVE
    assert row.tone is Tone.NEGATIVE


def test_a_negative_calmar_reads_as_a_net_loss():
    groups = build_groups([_card("Calmar Ratio", "-0.4")], timeframe_seconds=60)

    assert _row(groups, "CALMAR RATIO").badge_text == "Negative"


def test_the_ratio_buckets_are_the_ones_documented():
    groups = build_groups(
        [
            _card("Sharpe Ratio", "0.5"),
            _card("Sortino Ratio", "1.5"),
            _card("Calmar Ratio", "2.5"),
        ],
        timeframe_seconds=60,
    )

    assert _row(groups, "SHARPE RATIO").badge_text == "Average"
    assert _row(groups, "SORTINO RATIO").badge_text == "Good"
    assert _row(groups, "CALMAR RATIO").badge_text == "Strong"


def test_consecutive_losses_at_the_threshold_warn():
    groups = build_groups([_card("Max Consecutive Losses", "10")], timeframe_seconds=60)
    row = _row(groups, "MAX CONSECUTIVE LOSSES")

    assert row.badge_text == "Warning"
    assert row.badge_tone is Tone.NEGATIVE


def test_consecutive_losses_below_the_threshold_say_nothing():
    groups = build_groups([_card("Max Consecutive Losses", "9")], timeframe_seconds=60)

    assert _row(groups, "MAX CONSECUTIVE LOSSES").badge_text == ""


def test_the_drawdown_duration_converts_bars_with_the_runs_own_timeframe():
    """24 bars is a day at 1h and an hour at 1m — the whole reason this
    function takes the timeframe rather than assuming one."""
    hourly = build_groups(
        [_card("Max Drawdown Duration", "24", "bars")], timeframe_seconds=_ONE_HOUR
    )
    minutely = build_groups(
        [_card("Max Drawdown Duration", "24", "bars")], timeframe_seconds=60
    )

    assert _row(hourly, "MAX DRAWDOWN DURATION").info == "≈ 1 days"
    assert _row(minutely, "MAX DRAWDOWN DURATION").info == "≈ 0 days"


def test_a_non_numeric_value_gets_no_verdict_instead_of_raising():
    groups = build_groups([_card("Sharpe Ratio", "n/a")], timeframe_seconds=60)

    assert _row(groups, "SHARPE RATIO").badge_text == ""


def test_the_bar_divides_profit_against_loss():
    bar = build_gross_bar(
        gross_profit=1148.19, gross_loss=-9341.72, profit_factor=0.123
    )

    assert bar.profit_text == "+1,148.19"
    assert bar.loss_text == "-9,341.72"
    assert 0.1 < bar.profit_share < 0.12
    assert "profit factor 0.123" in bar.caption


def test_a_gross_loss_stored_negative_is_not_zeroed_out():
    """`BacktestMetrics.gross_loss` is the sum of losing trades' pnl, so it is
    `<= 0`. `max(x, 0.0)` here would have shown a losing run as all profit."""
    bar = build_gross_bar(gross_profit=100.0, gross_loss=-300.0, profit_factor=0.333)

    assert bar.loss_text == "-300.00"
    assert bar.profit_share == 0.25


def test_a_run_with_neither_profit_nor_loss_splits_the_bar_evenly():
    bar = build_gross_bar(gross_profit=0.0, gross_loss=0.0, profit_factor=0.0)

    assert bar.profit_share == 0.5


def test_an_infinite_profit_factor_reads_as_infinity():
    bar = build_gross_bar(
        gross_profit=100.0, gross_loss=0.0, profit_factor=float("inf")
    )

    assert "profit factor ∞" in bar.caption


def test_the_footer_says_what_the_numbers_were_computed_from():
    assert build_footer(total_closed_trades=891, fee_rate_percent=0.1) == (
        "Based on 891 closed trades · fee 0.1% per trade"
    )


def test_the_clipboard_text_carries_every_section_row_and_the_summaries():
    groups = build_groups(
        [_card("Gross Profit", "100", "USD"), _card("Sharpe Ratio", "2.5")],
        timeframe_seconds=60,
    )
    bar = build_gross_bar(gross_profit=100.0, gross_loss=-25.0, profit_factor=4.0)
    footer = build_footer(total_closed_trades=3, fee_rate_percent=0.1)

    text = build_clipboard_text(groups, bar, footer)

    assert text.startswith("BACKTEST DETAIL METRICS")
    assert "  GROSS PROFIT: 100 USD" in text
    assert "  SHARPE RATIO: 2.5 [Excellent]" in text
    assert text.rstrip().endswith(footer)
