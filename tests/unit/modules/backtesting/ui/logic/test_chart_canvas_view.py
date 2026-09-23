from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exit_reason import (
    ExitReason,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.chart_canvas_view import (
    _LONG_ENTRY_LABEL,
    _LONG_EXIT_LABEL,
    _LONG_EXIT_TP_LABEL,
    _SHORT_ENTRY_LABEL,
    _SHORT_EXIT_LABEL,
    _SHORT_EXIT_TP_LABEL,
    ChartDisplayMode,
    MarkerOutcomeFilter,
    MarkerSideFilter,
    TradeMarkerType,
    equity_curve_to_candles,
    equity_curve_to_line_data,
    filter_trades_for_markers,
    trade_flag_markers,
    trade_flag_markers_for_trades,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
    TAKE_PROFIT_COLOR,
)

_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_T1 = datetime(2026, 1, 2, tzinfo=UTC)


def test_chart_display_mode_has_exactly_the_3_bot_056_modes():
    assert {mode.value for mode in ChartDisplayMode} == {"ohlc", "equity", "both"}


def test_trade_marker_types_contain_explicit_long_and_short_semantics():
    # BOT-096: Distinguishes long entry/exit from future short entry/exit
    assert TradeMarkerType.LONG_ENTRY == "LONG_ENTRY"
    assert TradeMarkerType.LONG_EXIT == "LONG_EXIT"
    assert TradeMarkerType.SHORT_ENTRY == "SHORT_ENTRY"
    assert TradeMarkerType.SHORT_EXIT == "SHORT_EXIT"


def test_equity_curve_to_candles_flattens_ohlc_to_the_single_equity_value():
    equity_curve = [(_T0, 1000.0), (_T1, 1050.0)]

    candles = equity_curve_to_candles(equity_curve)

    assert candles == [
        (_T0.timestamp(), 1000.0, 1000.0, 1000.0, 1000.0),
        (_T1.timestamp(), 1050.0, 1050.0, 1050.0, 1050.0),
    ]


def test_equity_curve_to_line_data_splits_into_x_and_y_series():
    equity_curve = [(_T0, 1000.0), (_T1, 1050.0)]

    x_data, y_data = equity_curve_to_line_data(equity_curve)

    assert x_data == [_T0.timestamp(), _T1.timestamp()]
    assert y_data == [1000.0, 1050.0]


def _result_with_one_trade(
    side: PositionSide = PositionSide.LONG,
    exit_reason: ExitReason = ExitReason.STRATEGY_SIGNAL,
) -> BacktestResult:
    trade = Trade(
        symbol="ETHUSDT",
        entry_time=_T0,
        entry_price=100.0,
        exit_time=_T1,
        exit_price=110.0,
        quantity=1.0,
        pnl=10.0,
        pnl_percent=10.0,
        fees_paid=0.0,
        exit_reason=exit_reason,
        side=side,
    )
    metrics = BacktestMetrics.compute([trade], [(_T0, 1000.0), (_T1, 1010.0)], 1000.0)
    return BacktestResult(
        symbol="ETHUSDT",
        initial_balance=1000.0,
        final_balance=1010.0,
        trades=[trade],
        equity_curve=[(_T0, 1000.0), (_T1, 1010.0)],
        metrics=metrics,
    )


def test_trade_flag_markers_emits_one_long_entry_and_one_long_exit_per_trade():
    markers = trade_flag_markers(_result_with_one_trade())

    assert markers == [
        (_T0.timestamp(), 100.0, _LONG_ENTRY_LABEL, BULL_COLOR, "up"),
        (_T1.timestamp(), 110.0, _LONG_EXIT_LABEL, BEAR_COLOR, "down"),
    ]


def test_trade_flag_markers_emits_short_entry_and_exit_for_short_trade():
    short_trade = Trade(
        symbol="ETHUSDT",
        entry_time=_T0,
        entry_price=100.0,
        exit_time=_T1,
        exit_price=90.0,
        quantity=1.0,
        pnl=10.0,
        pnl_percent=10.0,
        fees_paid=0.0,
        side=PositionSide.SHORT,
    )
    result = BacktestResult(
        symbol="ETHUSDT",
        initial_balance=1000.0,
        final_balance=1010.0,
        trades=[short_trade],
        equity_curve=[(_T0, 1000.0), (_T1, 1010.0)],
        metrics=BacktestMetrics.compute(
            [short_trade], [(_T0, 1000.0), (_T1, 1010.0)], 1000.0
        ),
    )

    markers = trade_flag_markers(result)
    assert markers == [
        (_T0.timestamp(), 100.0, _SHORT_ENTRY_LABEL, BEAR_COLOR, "down"),
        (_T1.timestamp(), 90.0, _SHORT_EXIT_LABEL, BULL_COLOR, "up"),
    ]


def test_exit_marker_does_not_use_ambiguous_sell_or_short_label():
    # BOT-096 product truth: long exit must never be labeled "Sell" or "Short"
    markers = trade_flag_markers(_result_with_one_trade())
    exit_marker = markers[1]
    _, _, label, _, _ = exit_marker

    assert "SELL" not in label.upper()
    assert "SHORT" not in label.upper()
    assert "CLOSE" in label or "EXIT" in label


def test_short_trade_markers_use_truthful_short_labels_not_long():
    # BOT-111/BOT-050: a short entry/exit must never be labeled as if it
    # were a long trade — the two are opposite bets, not interchangeable.
    markers = trade_flag_markers(_result_with_one_trade(side=PositionSide.SHORT))

    assert markers == [
        (_T0.timestamp(), 100.0, _SHORT_ENTRY_LABEL, BEAR_COLOR, "down"),
        (_T1.timestamp(), 110.0, _SHORT_EXIT_LABEL, BULL_COLOR, "up"),
    ]
    assert "LONG" not in markers[0][2].upper()
    assert "LONG" not in markers[1][2].upper()


def test_take_profit_exit_gets_a_distinct_gold_marker_long():
    markers = trade_flag_markers(
        _result_with_one_trade(exit_reason=ExitReason.TAKE_PROFIT)
    )

    exit_marker = markers[1]
    assert exit_marker == (
        _T1.timestamp(),
        110.0,
        _LONG_EXIT_TP_LABEL,
        TAKE_PROFIT_COLOR,
        "down",
    )


def test_take_profit_exit_gets_a_distinct_gold_marker_short():
    markers = trade_flag_markers(
        _result_with_one_trade(
            side=PositionSide.SHORT, exit_reason=ExitReason.TAKE_PROFIT
        )
    )

    exit_marker = markers[1]
    assert exit_marker == (
        _T1.timestamp(),
        110.0,
        _SHORT_EXIT_TP_LABEL,
        TAKE_PROFIT_COLOR,
        "up",
    )


def test_non_take_profit_exit_reasons_keep_the_plain_side_based_label():
    # END_OF_BACKTEST / a strategy's own signal / a future stop-loss must
    # not be mislabeled as a take-profit — only ExitReason.TAKE_PROFIT gets
    # the gold marker (see trade_flag_markers' own docstring for why a
    # generic "(EMA)"-style suffix would be dishonest for other strategies).
    for reason in (ExitReason.STRATEGY_SIGNAL, ExitReason.END_OF_BACKTEST):
        markers = trade_flag_markers(_result_with_one_trade(exit_reason=reason))
        exit_marker = markers[1]
        assert exit_marker == (
            _T1.timestamp(),
            110.0,
            _LONG_EXIT_LABEL,
            BEAR_COLOR,
            "down",
        )


def test_trade_flag_markers_of_a_result_with_no_trades_is_empty():
    empty = BacktestResult(
        symbol="ETHUSDT",
        initial_balance=1000.0,
        final_balance=1000.0,
        trades=[],
        equity_curve=[(_T0, 1000.0)],
        metrics=BacktestMetrics.compute([], [(_T0, 1000.0)], 1000.0),
    )

    assert trade_flag_markers(empty) == []


# ---------------------------------------------------------------------------
# PROP-004 — chart marker filters
# ---------------------------------------------------------------------------


def _trade(
    *,
    pnl: float,
    pnl_percent: float,
    side: PositionSide = PositionSide.LONG,
) -> Trade:
    return Trade(
        symbol="ETHUSDT",
        entry_time=_T0,
        entry_price=100.0,
        exit_time=_T1,
        exit_price=100.0 + pnl,
        quantity=1.0,
        pnl=pnl,
        pnl_percent=pnl_percent,
        fees_paid=0.0,
        side=side,
    )


def test_trade_flag_markers_for_trades_matches_trade_flag_markers_of_the_result():
    result = _result_with_one_trade()

    assert trade_flag_markers_for_trades(result.trades) == trade_flag_markers(result)


def test_filter_all_outcome_and_side_keeps_every_trade():
    trades = [
        _trade(pnl=10.0, pnl_percent=1.0, side=PositionSide.LONG),
        _trade(pnl=-5.0, pnl_percent=-0.5, side=PositionSide.SHORT),
    ]

    filtered = filter_trades_for_markers(
        trades,
        outcome=MarkerOutcomeFilter.ALL,
        side=MarkerSideFilter.ALL,
        min_abs_pnl_percent=0.0,
    )

    assert filtered == trades


def test_wins_only_drops_a_break_even_or_losing_trade():
    win = _trade(pnl=10.0, pnl_percent=1.0)
    break_even = _trade(pnl=0.0, pnl_percent=0.0)
    loss = _trade(pnl=-10.0, pnl_percent=-1.0)

    filtered = filter_trades_for_markers(
        [win, break_even, loss],
        outcome=MarkerOutcomeFilter.WINS_ONLY,
        side=MarkerSideFilter.ALL,
        min_abs_pnl_percent=0.0,
    )

    assert filtered == [win]


def test_losses_only_keeps_a_break_even_trade_too():
    # Same sign convention as trade_log_filter.filter_trade_log_rows(): a
    # loss is `pnl <= 0`, so break-even (exactly 0) counts as a loss, not
    # neither — the two screens must never disagree about which bucket a
    # zero-PnL trade falls into.
    win = _trade(pnl=10.0, pnl_percent=1.0)
    break_even = _trade(pnl=0.0, pnl_percent=0.0)
    loss = _trade(pnl=-10.0, pnl_percent=-1.0)

    filtered = filter_trades_for_markers(
        [win, break_even, loss],
        outcome=MarkerOutcomeFilter.LOSSES_ONLY,
        side=MarkerSideFilter.ALL,
        min_abs_pnl_percent=0.0,
    )

    assert filtered == [break_even, loss]


def test_side_filter_keeps_only_the_requested_side():
    long_trade = _trade(pnl=1.0, pnl_percent=1.0, side=PositionSide.LONG)
    short_trade = _trade(pnl=1.0, pnl_percent=1.0, side=PositionSide.SHORT)

    assert filter_trades_for_markers(
        [long_trade, short_trade],
        outcome=MarkerOutcomeFilter.ALL,
        side=MarkerSideFilter.LONG_ONLY,
        min_abs_pnl_percent=0.0,
    ) == [long_trade]
    assert filter_trades_for_markers(
        [long_trade, short_trade],
        outcome=MarkerOutcomeFilter.ALL,
        side=MarkerSideFilter.SHORT_ONLY,
        min_abs_pnl_percent=0.0,
    ) == [short_trade]


def test_min_pnl_threshold_drops_trades_below_it_regardless_of_sign():
    small_win = _trade(pnl=1.0, pnl_percent=1.0)
    big_win = _trade(pnl=10.0, pnl_percent=6.0)
    big_loss = _trade(pnl=-10.0, pnl_percent=-6.0)

    filtered = filter_trades_for_markers(
        [small_win, big_win, big_loss],
        outcome=MarkerOutcomeFilter.ALL,
        side=MarkerSideFilter.ALL,
        min_abs_pnl_percent=5.0,
    )

    assert filtered == [big_win, big_loss]


def test_all_three_filters_combine_rather_than_override_each_other():
    matches = _trade(pnl=8.0, pnl_percent=8.0, side=PositionSide.SHORT)
    wrong_side = _trade(pnl=8.0, pnl_percent=8.0, side=PositionSide.LONG)
    wrong_outcome = _trade(pnl=-8.0, pnl_percent=-8.0, side=PositionSide.SHORT)
    below_threshold = _trade(pnl=1.0, pnl_percent=1.0, side=PositionSide.SHORT)

    filtered = filter_trades_for_markers(
        [matches, wrong_side, wrong_outcome, below_threshold],
        outcome=MarkerOutcomeFilter.WINS_ONLY,
        side=MarkerSideFilter.SHORT_ONLY,
        min_abs_pnl_percent=5.0,
    )

    assert filtered == [matches]
