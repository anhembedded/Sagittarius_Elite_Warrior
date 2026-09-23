from __future__ import annotations

from datetime import UTC, datetime, timedelta

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.performance_charts import (
    build_drawdown_chart_points,
    build_yearly_returns_rows,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.trade_log_row import (
    build_trade_log_rows,
    trade_log_rows_to_qml,
)

#: This file's parent directory is `ui`, same as every other module's own
#: `preview.py` — the fallback key `scripts/preview_qml.py::discover_previews()`
#: derives from the parent directory name would collide with theirs. Same fix
#: `modules/market_data/ui/preview.py` needed at PR 4.4b.
PREVIEW_KEY = "backtest"


def build_preview() -> QWidget:
    """Builds a standalone preview for the Backtest screen."""
    view = BackTestView()
    view_model = BackTestViewModel()
    view_model.strategyName = "EmaCrossoverStrategy"
    view_model.run_result.set_stat_cards(
        [
            {
                "title": "NET PROFIT",
                "value": "+1,420.50 USDT",
                "suffix": "+14.21%",
                "positive": True,
            },
            {
                "title": "MAX DRAWDOWN",
                "value": "-3.45%",
                "suffix": "",
                "positive": False,
            },
            {
                "title": "WIN RATE",
                "value": "62.50%",
                "suffix": "15/24",
                "positive": True,
            },
            {
                "title": "PROFIT FACTOR",
                "value": "1.84",
                "suffix": "",
                "positive": True,
            },
        ],
        [
            {"title": "Total Trades", "value": "24", "suffix": ""},
            {"title": "Winning Trades", "value": "15", "suffix": ""},
            {"title": "Losing Trades", "value": "9", "suffix": ""},
            {"title": "Gross Profit", "value": "3,120.00 USDT", "suffix": ""},
            {"title": "Gross Loss", "value": "-1,699.50 USDT", "suffix": ""},
            {"title": "Largest Winning Trade", "value": "450.00 USDT", "suffix": ""},
            {"title": "Largest Losing Trade", "value": "-210.00 USDT", "suffix": ""},
            {"title": "Average Profit/Loss", "value": "59.19 USDT", "suffix": ""},
        ],
    )
    view_model.run_result.set_limitations(
        [
            "Simulated on closed historical candle data",
            "Fixed 0.1% fee per side",
        ]
    )
    sample_trades = [
        Trade(
            symbol="ETHUSDT",
            entry_time=datetime(2024, 1, 2, 4, 0, tzinfo=UTC),
            entry_price=2250.0,
            exit_time=datetime(2024, 1, 2, 12, 0, tzinfo=UTC),
            exit_price=2310.0,
            quantity=1.0,
            pnl=60.0,
            pnl_percent=2.67,
            fees_paid=4.56,
            entry_reason="EMA Fast > Slow Cross",
            mae_percent=-1.85,
            mfe_percent=3.42,
        )
    ]
    rows = trade_log_rows_to_qml(build_trade_log_rows(sample_trades))
    view_model.trade_log.set_page_state(rows, total_count=len(rows), total_pages=1)

    # BOT-106D — a synthetic year-long equity curve (peak, drawdown, partial
    # recovery) so the drawdown chart and returns heatmap have something to
    # render standalone, without running a real backtest.
    start = datetime(2024, 1, 1, tzinfo=UTC)
    sample_equity_curve = [
        (start, 10_000.0),
        (start + timedelta(days=45), 11_500.0),
        (start + timedelta(days=90), 9_800.0),
        (start + timedelta(days=150), 10_600.0),
        (start + timedelta(days=220), 12_400.0),
        (start + timedelta(days=300), 11_900.0),
        (start + timedelta(days=364), 13_050.0),
    ]
    sample_result = BacktestResult.compute(
        symbol="ETHUSDT",
        initial_balance=10_000.0,
        final_balance=sample_equity_curve[-1][1],
        trades=sample_trades,
        equity_curve=sample_equity_curve,
    )
    view_model.run_result.set_drawdown_points(
        build_drawdown_chart_points(sample_result)
    )
    view_model.run_result.set_yearly_returns(build_yearly_returns_rows(sample_result))

    view.set_view_model(view_model)
    view.resize(1400, 850)
    return view
