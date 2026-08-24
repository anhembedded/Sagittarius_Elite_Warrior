from __future__ import annotations

from datetime import UTC, datetime

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.trade_log_row import (
    build_trade_log_rows,
    trade_log_rows_to_qml,
)


def build_preview() -> QWidget:
    """Builds a standalone preview for the Backtest screen."""
    view = BackTestView()
    view_model = BackTestViewModel()
    view_model.strategyName = "EmaCrossoverStrategy"
    view_model.set_stat_cards(
        [
            {
                "title": "LỢI NHUẬN RÒNG",
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
                "title": "TỶ LỆ THẮNG",
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
            {"title": "Tổng số lệnh", "value": "24", "suffix": ""},
            {"title": "Lệnh thắng", "value": "15", "suffix": ""},
            {"title": "Lệnh thua", "value": "9", "suffix": ""},
            {"title": "Lợi nhuận gộp", "value": "3,120.00 USDT", "suffix": ""},
            {"title": "Thua lỗ gộp", "value": "-1,699.50 USDT", "suffix": ""},
            {"title": "Lệnh thắng lớn nhất", "value": "450.00 USDT", "suffix": ""},
            {"title": "Lệnh thua lớn nhất", "value": "-210.00 USDT", "suffix": ""},
            {"title": "Lãi/lỗ trung bình", "value": "59.19 USDT", "suffix": ""},
        ],
    )
    view_model.set_limitations(
        [
            "Giả lập trên dữ liệu nến lịch sử đã đóng",
            "Phí cố định 0.1% mỗi chiều",
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
        )
    ]
    rows = trade_log_rows_to_qml(build_trade_log_rows(sample_trades))
    view_model.set_trade_log_page_state(rows, total_count=len(rows), total_pages=1)
    view.set_view_model(view_model)
    view.resize(1400, 850)
    return view
