"""The Backtest Trades table (`EPIC-033L`): raw values under column specs,
the profit's colour, and times written in the display time zone."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_trade_logs_panel import (
    BackTestTradeLogsPanel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.trade_log_row import (
    TradeLogRow,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.trade_table_model import (
    TradeTableModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)

_T0 = datetime(2026, 1, 1, 6, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 1, 18, 0, tzinfo=UTC)


def _row(index: int = 1, pnl: float = 10.0, side=PositionSide.LONG) -> TradeLogRow:
    return TradeLogRow(
        index=index,
        entry_time=_T0,
        entry_price=2000.0,
        exit_time=_T1,
        exit_price=2010.0,
        quantity=0.5,
        pnl=pnl,
        pnl_percent=pnl / 10,
        side=side,
    )


@pytest.fixture
def model(qapp):
    built = TradeTableModel()
    yield built
    built.deleteLater()


def _cell(model: TradeTableModel, row: int, key: str, role=Qt.ItemDataRole.DisplayRole):
    return model.data(model.index(row, model.column(key)), role)


def test_a_row_holds_raw_values_by_kind(model):
    model.set_rows([_row(index=216, side=PositionSide.SHORT)])

    assert _cell(model, 0, "number") == 216
    assert _cell(model, 0, "side") == "SHORT"
    assert _cell(model, 0, "entry_price") == 2000.0
    assert _cell(model, 0, "size") == 1000.0  # 0.5 at 2,000
    assert _cell(model, 0, "pnl") == 10.0


def test_a_gain_reads_bull_and_a_loss_bear_on_the_profit_columns(model):
    model.set_rows([_row(pnl=10.0), _row(index=2, pnl=-10.0)])
    foreground = Qt.ItemDataRole.ForegroundRole

    assert _cell(model, 0, "pnl", foreground) == QColor(BULL_COLOR)
    assert _cell(model, 0, "return", foreground) == QColor(BULL_COLOR)
    assert _cell(model, 1, "pnl", foreground) == QColor(BEAR_COLOR)
    assert _cell(model, 1, "entry_price", foreground) is None


def test_a_loss_keeps_its_sign_in_text(qapp):
    view_model = BackTestViewModel()
    panel = BackTestTradeLogsPanel(view_model)
    view_model.trade_log.set_rows([_row(pnl=-10.0)])

    text = panel.table.text(0, TradeTableModel.column("pnl"))

    assert text == "-10.00"
    panel.deleteLater()


@pytest.mark.parametrize(
    ("zone", "entry", "exit_"),
    [
        ("UTC", "2026-01-01 06:00:00", "2026-01-01 18:00:00"),
        ("Asia/Ho_Chi_Minh", "2026-01-01 13:00:00", "2026-01-02 01:00:00"),
    ],
)
def test_times_are_written_in_the_display_time_zone(qapp, zone, entry, exit_):
    """The display time zone is a view setting (data and runs are UTC); the
    table asks it each time it writes, so a change repaints every time."""
    view_model = BackTestViewModel()
    panel = BackTestTradeLogsPanel(view_model)
    view_model.time_range.displayTimezone = zone
    view_model.trade_log.set_rows([_row()])

    assert panel.table.text(0, TradeTableModel.column("entry_time")) == entry
    assert panel.table.text(0, TradeTableModel.column("exit_time")) == exit_
    panel.deleteLater()
