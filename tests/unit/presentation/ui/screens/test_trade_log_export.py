import csv
import json
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.domain.backtesting.exit_reason import ExitReason
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.trade_log_export import (
    export_trades_to_csv,
)

_T0 = datetime(2026, 1, 1, 6, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 1, 18, 0, tzinfo=UTC)


def _make_trade(pnl: float) -> Trade:
    return Trade(
        symbol="ETHUSDT",
        entry_time=_T0,
        entry_price=1939.5,
        exit_time=_T1,
        exit_price=1908.5,
        quantity=0.5,
        pnl=pnl,
        pnl_percent=pnl / 10,
        fees_paid=0.5,
        entry_reason="EMA Crossover 3/5 crossed above",
        exit_reason=ExitReason.STRATEGY_SIGNAL,
        metadata={"qml_score": 92},
    )


def test_export_writes_a_header_and_one_row_per_trade(tmp_path):
    trades = [_make_trade(10.0), _make_trade(-5.0)]
    csv_path = tmp_path / "trades.csv"

    export_trades_to_csv(trades, str(csv_path))

    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert rows[0] == [
        "index",
        "symbol",
        "entry_time",
        "entry_price",
        "exit_time",
        "exit_price",
        "quantity",
        "pnl",
        "pnl_percent",
        "fees_paid",
        "entry_reason",
        "exit_reason",
        "metadata",
    ]
    assert len(rows) == 3  # header + 2 trades
    assert rows[1][0] == "1"
    assert rows[1][1] == "ETHUSDT"
    assert rows[2][0] == "2"
    assert rows[1][10] == "EMA Crossover 3/5 crossed above"
    assert rows[1][11] == "strategy_signal"
    assert json.loads(rows[1][12]) == {"qml_score": 92}


def test_export_with_no_trades_writes_only_the_header(tmp_path):
    csv_path = tmp_path / "empty.csv"

    export_trades_to_csv([], str(csv_path))

    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert len(rows) == 1
