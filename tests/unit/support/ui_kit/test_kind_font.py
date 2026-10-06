"""A column whose digits align — a price, a quantity, money — is written in
the platform's fixed-pitch font, decided by the column's kind for every
table and never by a view (`EPIC-033N`, decision D6). Every other kind keeps
the application font. A model's one emphasis (a losing position, a candle's
close) makes a cell bold in its kind's font, so emphasis never takes the
digits out of line."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

import pytest
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QStyleOptionViewItem
from Sagittarius_Elite_Warrior.src.support.ui_kit.kind_font import kind_font
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)

_ROW = (64250.1, 0.015, 12.5, 3.2, "BTCUSDT", datetime(2026, 10, 6, tzinfo=UTC))


class _EveryKind(RowTableModel[tuple[DisplayValue, ...]]):
    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("price", "Price", ColumnKind.PRICE),
        ColumnSpec("quantity", "Quantity", ColumnKind.QUANTITY),
        ColumnSpec("money", "Money", ColumnKind.MONEY),
        ColumnSpec("percent", "Percent", ColumnKind.PERCENT),
        ColumnSpec("symbol", "Symbol", ColumnKind.TEXT, stretch=True),
        ColumnSpec("time", "Time", ColumnKind.TIMESTAMP),
    )
    #: The columns a row emphasises.
    emphasised: ClassVar[frozenset[str]] = frozenset()

    def _value(self, row: tuple[DisplayValue, ...], column: int) -> DisplayValue:
        return row[column]

    def _is_emphasised(self, row: tuple[DisplayValue, ...], column: int) -> bool:
        return self.COLUMNS[column].key in self.emphasised


class _Emphasising(_EveryKind):
    emphasised: ClassVar[frozenset[str]] = frozenset({"money", "symbol"})


def _font(table: SpecTable, key: str) -> QFont:
    """The cell's font as the view's own delegate paints it."""
    view = table.view
    index = view.model().index(0, table.model.column(key))
    option = QStyleOptionViewItem()
    view.itemDelegateForIndex(index).initStyleOption(option, index)
    return QFont(option.font)


def _table(model: _EveryKind) -> SpecTable:
    model.set_rows([_ROW])
    return SpecTable(model, object_name="tblKinds", empty_text="")


def _fixed_family() -> str:
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()


@pytest.mark.parametrize("key", ["price", "quantity", "money"])
def test_a_column_whose_digits_align_is_in_the_fixed_pitch_font(qapp, key) -> None:
    table = _table(_EveryKind())

    assert _font(table, key).family() == _fixed_family()


@pytest.mark.parametrize("key", ["percent", "symbol", "time"])
def test_every_other_column_keeps_the_application_font(qapp, key) -> None:
    table = _table(_EveryKind())

    assert _font(table, key).family() == QApplication.font().family()


def test_emphasis_is_bold_in_the_kinds_own_font(qapp) -> None:
    table = _table(_Emphasising())

    money, symbol = _font(table, "money"), _font(table, "symbol")

    assert money.bold() and money.family() == _fixed_family()
    assert symbol.bold() and symbol.family() == QApplication.font().family()
    assert not _font(table, "price").bold()


def test_the_kind_alone_decides_the_font(qapp) -> None:
    fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)

    assert kind_font(ColumnKind.PRICE) == fixed
    assert kind_font(ColumnKind.MONEY) == fixed
    assert kind_font(ColumnKind.TEXT) is None
    assert kind_font(ColumnKind.DURATION) is None
