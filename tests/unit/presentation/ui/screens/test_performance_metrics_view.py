from dataclasses import replace
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.out_of_sample_validation import (
    OutOfSampleValidation,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import Tone
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.performance_metrics_view import (
    build_extended_stat_cards,
    build_primary_stat_cards,
    build_result_warning_text,
    compute_max_drawdown_amount,
    stat_cards_to_qml,
)

_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_T1 = datetime(2026, 1, 2, tzinfo=UTC)
_T2 = datetime(2026, 1, 3, tzinfo=UTC)


def _trade(pnl: float) -> Trade:
    return Trade(
        symbol="ETHUSDT",
        entry_time=_T0,
        entry_price=100.0,
        exit_time=_T1,
        exit_price=100.0 + pnl,
        quantity=1.0,
        pnl=pnl,
        pnl_percent=pnl,
        fees_paid=0.0,
    )


def _result(
    trades: list[Trade],
    equity_curve,
    initial_balance: float = 1000.0,
    out_of_sample: OutOfSampleValidation | None = None,
) -> BacktestResult:
    final_balance = initial_balance + sum(t.pnl for t in trades)
    return BacktestResult(
        symbol="ETHUSDT",
        initial_balance=initial_balance,
        final_balance=final_balance,
        trades=trades,
        equity_curve=equity_curve,
        metrics=BacktestMetrics.compute(trades, equity_curve, initial_balance),
        out_of_sample=out_of_sample,
    )


def _result_with_net_profit_percent(percent: float) -> BacktestResult:
    """Bare `BacktestResult` with just enough to read `net_profit_percent`
    back off — used to build `OutOfSampleValidation.in_sample`/
    `out_of_sample` without needing real trades/equity curves."""
    metrics = BacktestMetrics.compute([], [], 1000.0)
    metrics = replace(metrics, net_profit_percent=percent)
    return BacktestResult(
        symbol="ETHUSDT",
        initial_balance=1000.0,
        final_balance=1000.0,
        trades=[],
        equity_curve=[],
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# compute_max_drawdown_amount
# ---------------------------------------------------------------------------


def test_max_drawdown_amount_matches_the_trough_of_the_max_percent_drawdown():
    # Peak 1200 -> trough 1000 is a $200 drop (16.67% of the 1200 peak) —
    # asserts the $ figure that goes WITH that specific trough, not just any
    # drop found somewhere in the series.
    equity_curve = [
        (_T0, 1000.0),
        (_T1, 1200.0),
        (_T2, 1000.0),
    ]

    assert compute_max_drawdown_amount(equity_curve) == 200.0


def test_max_drawdown_amount_agrees_with_backtest_metrics_percent():
    """Regression guard: the two independent calculations must describe the
    same trough, or the $ figure and the % badge would contradict each other
    on screen."""
    equity_curve = [(_T0, 1000.0), (_T1, 1500.0), (_T2, 1200.0)]
    metrics = BacktestMetrics.compute([], equity_curve, 1000.0)

    amount = compute_max_drawdown_amount(equity_curve)

    assert amount == 300.0
    assert metrics.max_drawdown_percent == (300.0 / 1500.0) * 100


def test_max_drawdown_amount_is_zero_for_a_monotonically_rising_curve():
    equity_curve = [(_T0, 1000.0), (_T1, 1100.0), (_T2, 1200.0)]
    assert compute_max_drawdown_amount(equity_curve) == 0.0


def test_max_drawdown_amount_of_an_empty_curve_is_zero():
    assert compute_max_drawdown_amount([]) == 0.0


# ---------------------------------------------------------------------------
# build_primary_stat_cards
# ---------------------------------------------------------------------------


def test_profitable_run_colors_every_card_bullish():
    result = _result(
        trades=[_trade(50.0), _trade(-10.0)],
        equity_curve=[(_T0, 1000.0), (_T1, 1050.0), (_T2, 1040.0)],
    )

    cards = build_primary_stat_cards(result)
    by_title = {card.title: card for card in cards}

    net_pnl = by_title["Tổng Lãi/Lỗ (Net PnL)"]
    assert net_pnl.value == "+40.00"
    assert net_pnl.value_tone is Tone.POSITIVE

    win_rate = by_title["Tỷ lệ thắng (Win Rate)"]
    assert win_rate.badge_text == "(1/2 lệnh)"

    profit_factor = by_title["Hệ số lãi (Profit Factor)"]
    assert profit_factor.value_tone is Tone.POSITIVE
    assert profit_factor.badge_text == ""  # not "Rủi ro" — profit_factor >= 1


def test_losing_run_colors_net_pnl_and_profit_factor_bearish():
    result = _result(
        trades=[_trade(-50.0), _trade(-10.0)],
        equity_curve=[(_T0, 1000.0), (_T1, 950.0), (_T2, 940.0)],
    )

    cards = build_primary_stat_cards(result)
    by_title = {card.title: card for card in cards}

    assert by_title["Tổng Lãi/Lỗ (Net PnL)"].value_tone is Tone.NEGATIVE
    profit_factor = by_title["Hệ số lãi (Profit Factor)"]
    assert profit_factor.value_tone is Tone.NEGATIVE
    assert profit_factor.badge_text == "Rủi ro"


def test_infinite_profit_factor_displays_as_the_infinity_symbol_not_a_crash():
    result = _result(
        trades=[_trade(50.0)],  # no losers -> gross_loss == 0 -> profit_factor = inf
        equity_curve=[(_T0, 1000.0), (_T1, 1050.0)],
    )

    cards = build_primary_stat_cards(result)
    profit_factor = next(c for c in cards if c.title == "Hệ số lãi (Profit Factor)")

    assert profit_factor.value == "∞"


def test_zero_trades_produces_four_cards_all_reading_zero_without_crashing():
    result = _result(trades=[], equity_curve=[(_T0, 1000.0), (_T1, 1000.0)])

    cards = build_primary_stat_cards(result)

    assert len(cards) == 4
    by_title = {card.title: card for card in cards}
    assert by_title["Tổng Lãi/Lỗ (Net PnL)"].value == "+0.00"
    assert by_title["Tỷ lệ thắng (Win Rate)"].value == "0.00%"
    assert by_title["Tỷ lệ thắng (Win Rate)"].badge_text == "(0/0 lệnh)"
    assert by_title["Hệ số lãi (Profit Factor)"].value == "0.000"


# ---------------------------------------------------------------------------
# build_extended_stat_cards / stat_cards_to_qml
# ---------------------------------------------------------------------------


def test_extended_cards_cover_every_remaining_metrics_field():
    result = _result(
        trades=[_trade(50.0), _trade(-10.0)],
        equity_curve=[(_T0, 1000.0), (_T1, 1050.0), (_T2, 1040.0)],
    )

    titles = {card.title for card in build_extended_stat_cards(result)}

    assert titles == {
        "Gross Profit",
        "Gross Loss",
        "Avg Trade",
        "Avg Winning Trade",
        "Avg Losing Trade",
        "Largest Winning Trade",
        "Largest Losing Trade",
        "Total Closed Trades",
        "Sharpe Ratio",  # BOT-106A
        "Sortino Ratio",  # BOT-106A
        "Calmar Ratio",  # BOT-106A
        "Max Drawdown Duration",  # BOT-106A
        "Max Consecutive Wins",  # BOT-106A
        "Max Consecutive Losses",  # BOT-106A
        "Total Fees Paid",  # BOT-079
    }


def test_extended_cards_format_the_new_bot_106a_metrics():
    result = _result(trades=[_trade(50.0)], equity_curve=[(_T0, 1000.0)])
    result = replace(
        result,
        metrics=replace(
            result.metrics,
            sharpe_ratio=1.5,
            sortino_ratio=2.25,
            calmar_ratio=-0.75,
            max_drawdown_duration_bars=12,
            max_consecutive_wins=4,
            max_consecutive_losses=2,
        ),
    )

    cards = {card.title: card for card in build_extended_stat_cards(result)}

    assert cards["Sharpe Ratio"].value == "1.50"
    assert cards["Sortino Ratio"].value == "2.25"
    assert cards["Calmar Ratio"].value == "-0.75"
    assert cards["Max Drawdown Duration"].value == "12"
    assert cards["Max Drawdown Duration"].suffix == "bars"
    assert cards["Max Consecutive Wins"].value == "4"
    assert cards["Max Consecutive Losses"].value == "2"


# ---------------------------------------------------------------------------
# BOT-079: fee transparency / trade frequency warning
# ---------------------------------------------------------------------------


def _fee_heavy_trade(fees: float) -> Trade:
    """807 round trips at a flat price -> zero gross edge, loss is 100% fees
    (same shape as the real BUG-002 log)."""
    return Trade(
        symbol="ETHUSDT",
        entry_time=_T0,
        entry_price=100.0,
        exit_time=_T1,
        exit_price=100.0,
        quantity=1.0,
        pnl=-fees,
        pnl_percent=-fees,
        fees_paid=fees,
    )


def test_net_pnl_badge_is_always_the_plain_signed_percent():
    """BOT-079 follow-up: an earlier version appended warning notes onto this
    badge — a small fixed-size `MetricCard` pill, not built for a sentence —
    which overflowed it. Warnings moved to `build_result_warning_text()`
    (its own full-width line); this badge stays exactly what BOT-055 shipped,
    warnings or not."""
    equity_curve = [(_T0, 1000.0)] * 40
    result = _result(trades=[_trade(50.0), _trade(-10.0)], equity_curve=equity_curve)

    net_pnl = next(
        c
        for c in build_primary_stat_cards(result)
        if c.title == "Tổng Lãi/Lỗ (Net PnL)"
    )

    assert net_pnl.badge_text == "+4.00%"
    assert net_pnl.badge_tone is Tone.POSITIVE


def test_result_warning_text_is_empty_when_neither_flag_fires():
    equity_curve = [(_T0, 1000.0)] * 40
    result = _result(trades=[_trade(50.0), _trade(-10.0)], equity_curve=equity_curve)

    assert build_result_warning_text(result) == ""


def test_result_warning_text_names_fee_dominance_and_high_frequency_together():
    trades = [_fee_heavy_trade(10.0) for _ in range(50)]
    equity_curve = [(_T0, 1000.0)] * 500  # 10 bars/trade -> also high frequency
    result = _result(trades, equity_curve)

    assert result.metrics.has_high_fee_ratio is True
    assert result.metrics.has_high_trade_frequency is True

    warning = build_result_warning_text(result)

    assert "Phí giao dịch" in warning
    assert "Tần suất giao dịch" in warning
    assert "10.0" in warning  # avg_bars_per_trade interpolated into the sentence


def test_extended_fees_card_turns_bearish_only_when_fee_ratio_warning_fires():
    healthy = _result(trades=[_trade(50.0), _trade(-10.0)], equity_curve=[])
    fee_heavy = _result(
        [_fee_heavy_trade(10.0) for _ in range(50)], [(_T0, 1000.0)] * 500
    )

    healthy_fees = next(
        c for c in build_extended_stat_cards(healthy) if c.title == "Total Fees Paid"
    )
    fee_heavy_fees = next(
        c for c in build_extended_stat_cards(fee_heavy) if c.title == "Total Fees Paid"
    )

    assert healthy_fees.value_tone is Tone.NEUTRAL
    assert fee_heavy_fees.value_tone is Tone.NEGATIVE


# ---------------------------------------------------------------------------
# BOT-080: in-sample / out-of-sample validation
# ---------------------------------------------------------------------------


def test_extended_cards_gain_two_cards_when_out_of_sample_is_present():
    out_of_sample = OutOfSampleValidation(
        in_sample=_result_with_net_profit_percent(20.0),
        out_of_sample=_result_with_net_profit_percent(15.0),
        in_sample_ratio=0.7,
    )
    result = _result(
        trades=[_trade(50.0)],
        equity_curve=[(_T0, 1000.0)],
        out_of_sample=out_of_sample,
    )

    titles = {card.title for card in build_extended_stat_cards(result)}

    assert "In-Sample Net Profit" in titles
    assert "Out-of-Sample Net Profit" in titles


def test_extended_cards_omit_out_of_sample_cards_when_the_range_was_too_short():
    result = _result(trades=[_trade(50.0)], equity_curve=[(_T0, 1000.0)])

    titles = {card.title for card in build_extended_stat_cards(result)}

    assert "In-Sample Net Profit" not in titles
    assert "Out-of-Sample Net Profit" not in titles


def test_out_of_sample_card_turns_bearish_only_when_divergence_is_high():
    healthy = _result(
        trades=[_trade(50.0)],
        equity_curve=[(_T0, 1000.0)],
        out_of_sample=OutOfSampleValidation(
            in_sample=_result_with_net_profit_percent(20.0),
            out_of_sample=_result_with_net_profit_percent(15.0),
            in_sample_ratio=0.7,
        ),
    )
    overfit = _result(
        trades=[_trade(50.0)],
        equity_curve=[(_T0, 1000.0)],
        out_of_sample=OutOfSampleValidation(
            in_sample=_result_with_net_profit_percent(50.0),
            out_of_sample=_result_with_net_profit_percent(-20.0),
            in_sample_ratio=0.7,
        ),
    )

    healthy_card = next(
        c
        for c in build_extended_stat_cards(healthy)
        if c.title == "Out-of-Sample Net Profit"
    )
    overfit_card = next(
        c
        for c in build_extended_stat_cards(overfit)
        if c.title == "Out-of-Sample Net Profit"
    )

    assert healthy_card.value_tone is Tone.NEUTRAL
    assert overfit_card.value_tone is Tone.NEGATIVE


def test_result_warning_text_includes_overfitting_note_when_divergence_is_high():
    result = _result(
        trades=[_trade(50.0)],
        equity_curve=[(_T0, 1000.0)] * 40,
        out_of_sample=OutOfSampleValidation(
            in_sample=_result_with_net_profit_percent(50.0),
            out_of_sample=_result_with_net_profit_percent(-20.0),
            in_sample_ratio=0.7,
        ),
    )

    warning = build_result_warning_text(result)

    assert "overfit" in warning
    assert "+50.00%" in warning
    assert "-20.00%" in warning


def test_result_warning_text_stays_empty_when_out_of_sample_is_close_to_in_sample():
    result = _result(
        trades=[_trade(50.0)],
        equity_curve=[(_T0, 1000.0)] * 40,
        out_of_sample=OutOfSampleValidation(
            in_sample=_result_with_net_profit_percent(20.0),
            out_of_sample=_result_with_net_profit_percent(15.0),
            in_sample_ratio=0.7,
        ),
    )

    assert build_result_warning_text(result) == ""


def test_stat_cards_to_qml_uses_qml_property_names():
    result = _result(trades=[_trade(50.0)], equity_curve=[(_T0, 1000.0), (_T1, 1050.0)])

    qml_cards = stat_cards_to_qml(build_primary_stat_cards(result))

    assert all(
        set(card.keys())
        == {"title", "value", "valueTone", "suffix", "badgeText", "badgeTone"}
        for card in qml_cards
    )
