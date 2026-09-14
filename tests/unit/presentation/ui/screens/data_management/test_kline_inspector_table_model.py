"""`KLineInspectorTableModel` — the eight columns of one candle.

Rewritten for `EPIC-025` PR 0.4b. The previous version asserted page
arithmetic (`total_pages`, `set_page`, `jump_to_date`) against a model whose
only reader had stopped paginating in `EPIC-015`; the formatting assertions it
made are kept, because the formatting is what the user actually reads.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QModelIndex, Qt
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.kline_inspector_table_model import (
    BEARISH_COLOR,
    BULLISH_COLOR,
    KLineInspectorTableModel,
    market_data_to_kline_row,
)

_BASE = datetime(2026, 7, 25, 13, 46, tzinfo=UTC)


def _kline(
    index: int = 0,
    *,
    open_price: float = 100.0,
    close_price: float = 101.0,
    volume: float = 1_500_000.0,
    trades: int = 42,
) -> MarketData:
    open_time = _BASE + timedelta(minutes=index)
    return MarketData(
        symbol="BTCUSDT",
        interval="1m",
        open_time=open_time,
        close_time=open_time + timedelta(minutes=1),
        open_price=open_price,
        high_price=max(open_price, close_price) + 1,
        low_price=min(open_price, close_price) - 1,
        close_price=close_price,
        volume=volume,
        quote_asset_volume=2_500.0,
        number_of_trades=trades,
        taker_buy_base_asset_volume=1.0,
        taker_buy_quote_asset_volume=1.0,
    )


@pytest.fixture
def model(qapp):
    return KLineInspectorTableModel()


def _text(model: KLineInspectorTableModel, row: int, column: int) -> str:
    return str(model.data(model.index(row, column), Qt.ItemDataRole.DisplayRole))


# ---------------------------------------------------------------------------
# The table a QTableView sees
# ---------------------------------------------------------------------------


def test_the_model_declares_eight_columns_with_headers(model):
    assert model.columnCount() == 8
    assert [
        model.headerData(column, Qt.Orientation.Horizontal)
        for column in range(model.columnCount())
    ] == [
        "Time (UTC)",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "Change",
        "Trades",
    ]


def test_every_candle_becomes_one_row(model):
    model.set_klines([_kline(0), _kline(1), _kline(2)])

    assert model.rowCount() == 3
    assert model.total_records == 3


def test_a_second_load_replaces_the_first(model):
    """Opening the inspector on another shard must not append to the last
    one's candles."""
    model.set_klines([_kline(0), _kline(1)])

    model.set_klines([_kline(0)])

    assert model.rowCount() == 1


def test_clear_empties_the_table(model):
    model.set_klines([_kline(0)])

    model.clear()

    assert model.rowCount() == 0
    assert model.row_for(model.index(0, 0)) is None


def test_an_invalid_index_has_no_row(model):
    model.set_klines([_kline(0)])

    assert model.row_for(QModelIndex()) is None


def test_each_column_renders_its_own_field(model):
    model.set_klines([_kline(0, open_price=100.0, close_price=101.0, trades=42)])

    assert (
        _text(model, 0, KLineInspectorTableModel.TIME_COLUMN) == "2026-07-25 13:46:00"
    )
    assert _text(model, 0, KLineInspectorTableModel.OPEN_COLUMN) == "100.00"
    assert _text(model, 0, KLineInspectorTableModel.HIGH_COLUMN) == "102.00"
    # Four decimals, not two: 99 is below the 100.0 threshold that switches
    # the price format to grouped-with-cents.
    assert _text(model, 0, KLineInspectorTableModel.LOW_COLUMN) == "99.0000"
    assert _text(model, 0, KLineInspectorTableModel.CLOSE_COLUMN) == "101.00"
    assert _text(model, 0, KLineInspectorTableModel.VOLUME_COLUMN) == "1.50M"
    assert _text(model, 0, KLineInspectorTableModel.CHANGE_COLUMN) == "+1.00%"
    assert _text(model, 0, KLineInspectorTableModel.TRADES_COLUMN) == "42"


# ---------------------------------------------------------------------------
# Formatting, which is what the user reads
# ---------------------------------------------------------------------------


def test_a_price_below_one_keeps_its_significant_digits():
    """A `0.00001234` coin rendered as `0.00` would be a lie about the
    price."""
    row = market_data_to_kline_row(_kline(open_price=0.00001234, close_price=0.000013))

    assert row.open_str == "0.00001234"


def test_a_large_price_is_grouped_and_a_mid_price_keeps_four_decimals():
    assert market_data_to_kline_row(_kline(open_price=64_235.5)).open_str == "64,235.50"
    assert market_data_to_kline_row(_kline(open_price=12.5)).open_str == "12.5000"


def test_volume_is_abbreviated_by_magnitude():
    assert market_data_to_kline_row(_kline(volume=2_400_000.0)).volume_str == "2.40M"
    assert market_data_to_kline_row(_kline(volume=2_400.0)).volume_str == "2.40K"
    assert market_data_to_kline_row(_kline(volume=2.4)).volume_str == "2.4"


def test_the_change_percentage_carries_its_sign():
    assert (
        market_data_to_kline_row(
            _kline(open_price=100.0, close_price=101.0)
        ).change_pct_str
        == "+1.00%"
    )
    assert (
        market_data_to_kline_row(
            _kline(open_price=100.0, close_price=99.0)
        ).change_pct_str
        == "-1.00%"
    )


def test_a_zero_open_price_does_not_divide_by_zero():
    assert (
        market_data_to_kline_row(_kline(open_price=0.0, close_price=5.0)).change_pct_str
        == "+0.00%"
    )


def test_an_unchanged_candle_counts_as_bullish():
    """A doji is not a fall, and the colour has to pick one."""
    assert market_data_to_kline_row(
        _kline(open_price=100.0, close_price=100.0)
    ).is_bullish


# ---------------------------------------------------------------------------
# The presentation roles
# ---------------------------------------------------------------------------


def test_the_close_and_change_cells_carry_the_candle_direction(model):
    model.set_klines(
        [
            _kline(0, open_price=100.0, close_price=101.0),
            _kline(1, open_price=100.0, close_price=99.0),
        ]
    )

    for column in (
        KLineInspectorTableModel.CLOSE_COLUMN,
        KLineInspectorTableModel.CHANGE_COLUMN,
    ):
        assert (
            model.data(model.index(0, column), Qt.ItemDataRole.ForegroundRole)
            == BULLISH_COLOR
        )
        assert (
            model.data(model.index(1, column), Qt.ItemDataRole.ForegroundRole)
            == BEARISH_COLOR
        )


def test_no_other_cell_is_coloured(model):
    """ADR D21: colour only where it carries meaning. `Open` and `High` do
    not carry a direction."""
    model.set_klines([_kline(0)])

    for column in (
        KLineInspectorTableModel.TIME_COLUMN,
        KLineInspectorTableModel.OPEN_COLUMN,
        KLineInspectorTableModel.HIGH_COLUMN,
        KLineInspectorTableModel.LOW_COLUMN,
        KLineInspectorTableModel.VOLUME_COLUMN,
        KLineInspectorTableModel.TRADES_COLUMN,
    ):
        assert (
            model.data(model.index(0, column), Qt.ItemDataRole.ForegroundRole) is None
        )


def test_every_cell_is_monospaced_and_the_close_is_bold(model):
    model.set_klines([_kline(0)])

    time_font = model.data(
        model.index(0, KLineInspectorTableModel.TIME_COLUMN), Qt.ItemDataRole.FontRole
    )
    close_font = model.data(
        model.index(0, KLineInspectorTableModel.CLOSE_COLUMN), Qt.ItemDataRole.FontRole
    )

    assert time_font.styleHint() == time_font.StyleHint.Monospace
    assert time_font.bold() is False
    assert close_font.bold() is True


def test_the_numeric_columns_are_right_aligned(model):
    model.set_klines([_kline(0)])

    def alignment(column: int):
        return model.data(model.index(0, column), Qt.ItemDataRole.TextAlignmentRole)

    assert alignment(KLineInspectorTableModel.CLOSE_COLUMN) & int(
        Qt.AlignmentFlag.AlignRight
    )
    assert alignment(KLineInspectorTableModel.TIME_COLUMN) is None
