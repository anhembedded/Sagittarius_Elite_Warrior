from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.domain.backtesting.exit_reason import ExitReason
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.trade_log_row import (
    TradeLogRow,
    build_trade_log_rows,
    trade_log_row_to_qml,
    trade_log_rows_to_qml,
)

_T0 = datetime(2026, 1, 1, 6, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 1, 18, 0, tzinfo=UTC)


def _make_trade(pnl: float, pnl_percent: float = 1.0) -> Trade:
    return Trade(
        symbol="ETHUSDT",
        entry_time=_T0,
        entry_price=1939.5,
        exit_time=_T1,
        exit_price=1908.5,
        quantity=0.5,
        pnl=pnl,
        pnl_percent=pnl_percent,
        fees_paid=0.5,
        entry_reason="EMA Crossover 3/5 crossed above",
        exit_reason=ExitReason.STRATEGY_SIGNAL,
        metadata={"qml_score": 92},
    )


def test_build_trade_log_rows_indexes_from_1_in_order():
    trades = [_make_trade(10.0), _make_trade(-5.0), _make_trade(20.0)]

    rows = build_trade_log_rows(trades)

    assert [row.index for row in rows] == [1, 2, 3]
    assert rows[1].pnl == -5.0


def test_trade_log_row_to_qml_formats_the_position_label_with_stable_index():
    row = TradeLogRow(
        index=216,
        entry_time=_T0,
        entry_price=1939.5,
        exit_time=_T1,
        exit_price=1908.5,
        quantity=0.5,
        pnl=34.66,
        pnl_percent=3.61,
    )

    qml_row = trade_log_row_to_qml(row)

    assert qml_row["positionLabel"] == "#216 vị thế mua"
    assert qml_row["index"] == "216"


def test_trade_log_row_to_qml_colors_winning_pnl_bull_and_losing_pnl_bear():
    win_row = TradeLogRow(1, _T0, 100.0, _T1, 110.0, 1.0, 10.0, 10.0)
    loss_row = TradeLogRow(2, _T0, 100.0, _T1, 90.0, 1.0, -10.0, -10.0)

    assert trade_log_row_to_qml(win_row)["pnlColor"] == BULL_COLOR
    assert trade_log_row_to_qml(loss_row)["pnlColor"] == BEAR_COLOR


def test_trade_log_row_to_qml_signs_pnl_and_return_text():
    win_row = TradeLogRow(1, _T0, 100.0, _T1, 110.0, 1.0, 10.0, 10.0)
    loss_row = TradeLogRow(2, _T0, 100.0, _T1, 90.0, 1.0, -10.0, -10.0)

    assert trade_log_row_to_qml(win_row)["pnlText"] == "+10.00 USD"
    assert trade_log_row_to_qml(win_row)["returnText"] == "+10.00%"
    assert trade_log_row_to_qml(loss_row)["pnlText"] == "-10.00 USD"
    assert trade_log_row_to_qml(loss_row)["returnText"] == "-10.00%"


def test_trade_log_row_to_qml_uses_compact_k_notation_above_1000():
    big_row = TradeLogRow(
        1, _T0, 2000.0, _T1, 2010.0, 1.0, 10.0, 0.5
    )  # 2000 * 1 = 2000
    small_row = TradeLogRow(2, _T0, 100.0, _T1, 110.0, 1.0, 10.0, 10.0)  # 100 * 1 = 100

    assert trade_log_row_to_qml(big_row)["positionSizeText"] == "2.00 K USD"
    assert trade_log_row_to_qml(small_row)["positionSizeText"] == "100.00 USD"


def test_trade_log_rows_to_qml_converts_every_row():
    rows = [
        TradeLogRow(1, _T0, 100.0, _T1, 110.0, 1.0, 10.0, 10.0),
        TradeLogRow(2, _T0, 100.0, _T1, 90.0, 1.0, -10.0, -10.0),
    ]

    qml_rows = trade_log_rows_to_qml(rows)

    assert len(qml_rows) == 2
    assert all(isinstance(row, dict) for row in qml_rows)


# ================= BOT-045: Trade Journal Detail =================


def test_build_trade_log_rows_carries_entry_exit_reason_and_metadata():
    trades = [_make_trade(10.0)]

    rows = build_trade_log_rows(trades)

    assert rows[0].entry_reason == "EMA Crossover 3/5 crossed above"
    assert rows[0].exit_reason is ExitReason.STRATEGY_SIGNAL
    assert rows[0].metadata == {"qml_score": 92}


def test_trade_log_row_to_qml_falls_back_to_a_placeholder_for_a_blank_entry_reason():
    row = TradeLogRow(1, _T0, 100.0, _T1, 110.0, 1.0, 10.0, 10.0, entry_reason="")

    qml_row = trade_log_row_to_qml(row)

    assert qml_row["entryReasonText"] == "—"


def test_trade_log_row_to_qml_translates_exit_reason_to_vietnamese():
    row = TradeLogRow(
        1,
        _T0,
        100.0,
        _T1,
        110.0,
        1.0,
        10.0,
        10.0,
        exit_reason=ExitReason.END_OF_BACKTEST,
    )

    qml_row = trade_log_row_to_qml(row)

    assert qml_row["exitReasonText"] == "Kết thúc backtest"


def test_trade_log_row_to_qml_formats_duration_as_hours_and_minutes():
    row = TradeLogRow(1, _T0, 100.0, _T1, 110.0, 1.0, 10.0, 10.0)  # T0=06:00, T1=18:00

    qml_row = trade_log_row_to_qml(row)

    assert qml_row["durationText"] == "12h 00m"


def test_trade_log_row_to_qml_renders_metadata_items_with_humanized_labels():
    row = TradeLogRow(
        1,
        _T0,
        100.0,
        _T1,
        110.0,
        1.0,
        10.0,
        10.0,
        metadata={"qml_score": 92},
    )

    qml_row = trade_log_row_to_qml(row)

    assert qml_row["metadataItems"] == [{"label": "Qml Score", "value": "92"}]


def test_trade_log_row_to_qml_renders_no_metadata_items_when_metadata_is_empty():
    row = TradeLogRow(1, _T0, 100.0, _T1, 110.0, 1.0, 10.0, 10.0, metadata={})

    qml_row = trade_log_row_to_qml(row)

    assert qml_row["metadataItems"] == []
