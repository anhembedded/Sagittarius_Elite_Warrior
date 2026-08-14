from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)
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
    trades: list[Trade], equity_curve, initial_balance: float = 1000.0
) -> BacktestResult:
    final_balance = initial_balance + sum(t.pnl for t in trades)
    return BacktestResult(
        symbol="ETHUSDT",
        initial_balance=initial_balance,
        final_balance=final_balance,
        trades=trades,
        equity_curve=equity_curve,
        metrics=BacktestMetrics.compute(trades, equity_curve, initial_balance),
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
    assert net_pnl.value_color == BULL_COLOR

    win_rate = by_title["Tỷ lệ thắng (Win Rate)"]
    assert win_rate.badge_text == "(1/2 lệnh)"

    profit_factor = by_title["Hệ số lãi (Profit Factor)"]
    assert profit_factor.value_color == BULL_COLOR
    assert profit_factor.badge_text == ""  # not "Rủi ro" — profit_factor >= 1


def test_losing_run_colors_net_pnl_and_profit_factor_bearish():
    result = _result(
        trades=[_trade(-50.0), _trade(-10.0)],
        equity_curve=[(_T0, 1000.0), (_T1, 950.0), (_T2, 940.0)],
    )

    cards = build_primary_stat_cards(result)
    by_title = {card.title: card for card in cards}

    assert by_title["Tổng Lãi/Lỗ (Net PnL)"].value_color == BEAR_COLOR
    profit_factor = by_title["Hệ số lãi (Profit Factor)"]
    assert profit_factor.value_color == BEAR_COLOR
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
        "Total Fees Paid",  # BOT-079
    }


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
    assert net_pnl.badge_color == BULL_COLOR


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

    assert healthy_fees.value_color == ""
    assert fee_heavy_fees.value_color == BEAR_COLOR


def test_stat_cards_to_qml_uses_qml_property_names():
    result = _result(trades=[_trade(50.0)], equity_curve=[(_T0, 1000.0), (_T1, 1050.0)])

    qml_cards = stat_cards_to_qml(build_primary_stat_cards(result))

    assert all(
        set(card.keys())
        == {"title", "value", "valueColor", "suffix", "badgeText", "badgeColor"}
        for card in qml_cards
    )
