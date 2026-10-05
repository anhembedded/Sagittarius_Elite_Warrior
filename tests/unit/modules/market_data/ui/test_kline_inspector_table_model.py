"""`KLineInspectorTableModel` — the eight columns of one candle.

Rewritten for `EPIC-025` PR 0.4b. The previous version asserted page
arithmetic (`total_pages`, `set_page`, `jump_to_date`) against a model whose
only reader had stopped paginating in `EPIC-015`. Since `EPIC-033N` the cells
hold values and the application's formatter writes them; `_text` reads a cell
the way the table writes it.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QFont
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.kline_inspector_table_model import (
    BEARISH_COLOR,
    BULLISH_COLOR,
    KLineInspectorTableModel,
    market_data_to_kline_row,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import write_value

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


def _text(model: KLineInspectorTableModel, row: int, key: str) -> str:
    column = KLineInspectorTableModel.column(key)
    raw = model.data(model.index(row, column), Qt.ItemDataRole.DisplayRole)
    return write_value(KLineInspectorTableModel.COLUMNS[column].kind, raw)


# ---------------------------------------------------------------------------
# The table a QTableView sees
# ---------------------------------------------------------------------------


def test_the_model_declares_eight_columns_with_headers(model):
    assert model.columnCount() == 8
    assert [
        model.headerData(column, Qt.Orientation.Horizontal)
        for column in range(model.columnCount())
    ] == [
        "Time",
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


def test_each_column_is_written_by_its_kind(model):
    model.set_klines([_kline(0, open_price=100.0, close_price=101.0, trades=42)])

    assert _text(model, 0, "time") == "2026-07-25 13:46:00"
    assert _text(model, 0, "open") == "100.0000"
    assert _text(model, 0, "high") == "102.0000"
    assert _text(model, 0, "low") == "99.0000"
    assert _text(model, 0, "close") == "101.0000"
    assert _text(model, 0, "volume") == "1,500,000"
    assert _text(model, 0, "change") == "1.00%"
    assert _text(model, 0, "trades") == "42"


def test_a_price_below_one_keeps_its_significant_digits(model):
    """A `0.00001234` coin written as `0.00` would be a lie about the
    price."""
    model.set_klines([_kline(open_price=0.00001234, close_price=0.000013)])

    assert _text(model, 0, "open") == "0.00001234"


def test_a_large_price_is_grouped_to_the_cent(model):
    model.set_klines([_kline(open_price=64_235.5, close_price=64_300.0)])

    assert _text(model, 0, "open") == "64,235.50"


def test_the_change_is_a_signed_percentage():
    rising = market_data_to_kline_row(_kline(open_price=100.0, close_price=101.0))
    falling = market_data_to_kline_row(_kline(open_price=100.0, close_price=99.0))

    assert rising.change_percent == pytest.approx(1.0)
    assert falling.change_percent == pytest.approx(-1.0)


def test_a_zero_open_price_does_not_divide_by_zero():
    row = market_data_to_kline_row(_kline(open_price=0.0, close_price=5.0))

    assert row.change_percent == 0.0


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
        KLineInspectorTableModel.column("close"),
        KLineInspectorTableModel.column("change"),
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

    for column in map(
        KLineInspectorTableModel.column,
        ("time", "open", "high", "low", "volume", "trades"),
    ):
        assert (
            model.data(model.index(0, column), Qt.ItemDataRole.ForegroundRole) is None
        )


def test_only_the_close_is_bold_and_no_cell_sets_a_font_family(model):
    """`ui-presentation-rule.md` §1: a widget may derive size or weight from
    the system font, never a family — the monospace family is gone."""
    model.set_klines([_kline(0)])

    time_font = model.data(
        model.index(0, KLineInspectorTableModel.column("time")),
        Qt.ItemDataRole.FontRole,
    )
    close_font = model.data(
        model.index(0, KLineInspectorTableModel.column("close")),
        Qt.ItemDataRole.FontRole,
    )

    assert time_font is None
    assert close_font.bold() is True
    assert close_font.family() == QFont().family()
