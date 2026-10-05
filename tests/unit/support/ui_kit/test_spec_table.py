"""`RowTableModel` + `SpecTable`: a table declared by its column specs and
shown the one way every table of the application is (`EPIC-033N`)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import pytest
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QAbstractItemView
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)


@dataclass(frozen=True)
class _Fill:
    symbol: str
    price: float | None


class _FillsModel(RowTableModel[_Fill]):
    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("symbol", "Symbol", ColumnKind.TEXT, stretch=True),
        ColumnSpec("price", "Price", ColumnKind.PRICE),
    )

    def _value(self, row: _Fill, column: int) -> DisplayValue:
        return (row.symbol, row.price)[column]


@pytest.fixture
def table(qapp) -> SpecTable[_Fill]:
    return SpecTable(_FillsModel(), object_name="tblFills", empty_text="No fills.")


def _fills(*rows: tuple[str, float | None]) -> list[_Fill]:
    return [_Fill(symbol, price) for symbol, price in rows]


def test_a_column_is_found_by_its_key_and_an_unknown_key_says_so():
    assert _FillsModel.column("price") == 1
    with pytest.raises(KeyError, match="no column 'volume'"):
        _FillsModel.column("volume")


def test_the_header_is_the_specs_titles(table):
    model = table.view.model()

    assert [
        model.headerData(column, Qt.Orientation.Horizontal)
        for column in range(model.columnCount())
    ] == ["Symbol", "Price"]


def test_a_cell_holds_the_raw_value_and_shows_it_by_kind(table):
    table.model.set_rows(_fills(("BTCUSDT", 64250.1)))

    source = table.model
    assert source.data(source.index(0, 1), Qt.ItemDataRole.DisplayRole) == 64250.1
    assert table.text(0, 1) == "64,250.10"


def test_an_unknown_value_is_an_empty_cell(table):
    table.model.set_rows(_fills(("BTCUSDT", None)))

    assert table.text(0, 1) == ""


def test_a_stale_index_has_no_value(table):
    table.model.set_rows(_fills(("BTCUSDT", 1.0)))

    assert table.model.data(QModelIndex()) is None
    assert table.model.data(table.model.index(5, 0)) is None


def test_the_selected_row_is_the_one_the_user_sees_after_sorting(table):
    """The view's indexes are the proxy's; a row read without mapping would
    be the model's row at the same position — a different fill."""
    table.model.set_rows(_fills(("BTCUSDT", 60000.0), ("ETHUSDT", 3000.0)))
    table.sort_by(_FillsModel.column("price"))

    table.view.selectRow(1)

    selected = table.selected_row()
    assert selected is not None
    assert selected.symbol == "BTCUSDT"


def test_nothing_selected_reads_as_none(table):
    table.model.set_rows(_fills(("BTCUSDT", 1.0)))

    assert table.selected_row() is None
    assert table.selected_rows() == []


def test_the_view_behaves_the_one_way_every_table_does(table):
    view = table.view

    assert view.objectName() == "tblFills"
    assert view.selectionBehavior() is QAbstractItemView.SelectionBehavior.SelectRows
    assert view.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
    assert view.isSortingEnabled() is True


def test_the_instruction_shows_while_there_are_no_rows(table):
    assert table.body.currentWidget() is not table.view
    assert table.body.instruction == "No fills."

    table.model.set_rows(_fills(("BTCUSDT", 1.0)))
    assert table.body.currentWidget() is table.view

    table.model.clear()
    assert table.body.currentWidget() is not table.view
