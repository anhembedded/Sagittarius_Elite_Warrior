from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exit_reason import (
    ExitReason,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.trade_log_row import (
    TradeLogRow,
    build_trade_log_rows,
    trade_details,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
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


def test_build_trade_log_rows_carries_the_trades_side_through():
    long_trade = _make_trade(10.0)
    short_trade = Trade(
        symbol="ETHUSDT",
        entry_time=_T0,
        entry_price=1939.5,
        exit_time=_T1,
        exit_price=1908.5,
        quantity=0.5,
        pnl=15.0,
        pnl_percent=1.5,
        fees_paid=0.5,
        side=PositionSide.SHORT,
    )

    rows = build_trade_log_rows([long_trade, short_trade])

    assert rows[0].side is PositionSide.LONG
    assert rows[1].side is PositionSide.SHORT


# ================= BOT-045: Trade Journal Detail =================


def test_build_trade_log_rows_carries_entry_exit_reason_and_metadata():
    trades = [_make_trade(10.0)]

    rows = build_trade_log_rows(trades)

    assert rows[0].entry_reason == "EMA Crossover 3/5 crossed above"
    assert rows[0].exit_reason is ExitReason.STRATEGY_SIGNAL
    assert rows[0].metadata == {"qml_score": 92}


# ================= BOT-106D: MAE/MFE =================


def test_build_trade_log_rows_carries_mae_and_mfe_through():
    trade = Trade(
        symbol="ETHUSDT",
        entry_time=_T0,
        entry_price=1939.5,
        exit_time=_T1,
        exit_price=1908.5,
        quantity=0.5,
        pnl=10.0,
        pnl_percent=1.0,
        fees_paid=0.5,
        mae_percent=-3.21,
        mfe_percent=5.67,
    )

    rows = build_trade_log_rows([trade])

    assert rows[0].mae_percent == -3.21
    assert rows[0].mfe_percent == 5.67


def test_build_trade_log_rows_defaults_mae_mfe_to_zero():
    """0.0 is `Trade`'s own "no excursion observed" convention, not a bug —
    every pre-`BOT-106B` construction site still gets a row."""
    rows = build_trade_log_rows([_make_trade(10.0)])

    assert rows[0].mae_percent == 0.0
    assert rows[0].mfe_percent == 0.0


# ================= BOT-045: the selected trade's journal =================


def test_a_blank_entry_reason_reads_as_a_dash():
    row = TradeLogRow(1, _T0, 100.0, _T1, 110.0, 1.0, 10.0, 10.0, entry_reason="")

    assert dict(trade_details(row))["Entry reason"] == "—"


def test_the_exit_reason_reads_as_words():
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

    assert dict(trade_details(row))["Exit reason"] == "End of backtest"


def test_the_duration_reads_in_hours_and_minutes():
    row = TradeLogRow(1, _T0, 100.0, _T1, 110.0, 1.0, 10.0, 10.0)  # 06:00 to 18:00

    assert dict(trade_details(row))["Duration"] == "12h 00m"


def test_excursions_are_signed_percentages():
    row = TradeLogRow(
        1, _T0, 100.0, _T1, 110.0, 1.0, 10.0, 10.0, mae_percent=-3.21, mfe_percent=5.67
    )

    details = dict(trade_details(row))

    assert details["Worst excursion (MAE)"] == "-3.21%"
    assert details["Best excursion (MFE)"] == "+5.67%"


def test_a_strategys_metadata_follows_with_readable_labels_in_its_order():
    row = TradeLogRow(
        1,
        _T0,
        100.0,
        _T1,
        110.0,
        1.0,
        10.0,
        10.0,
        metadata={"qml_score": 92, "zone": "demand"},
    )

    labels = [label for label, _text in trade_details(row)]

    assert labels[-2:] == ["Qml Score", "Zone"]
    assert dict(trade_details(row))["Qml Score"] == "92"


def test_no_metadata_adds_no_line():
    row = TradeLogRow(1, _T0, 100.0, _T1, 110.0, 1.0, 10.0, 10.0, metadata={})

    assert [label for label, _text in trade_details(row)] == [
        "Entry reason",
        "Exit reason",
        "Duration",
        "Worst excursion (MAE)",
        "Best excursion (MFE)",
    ]
