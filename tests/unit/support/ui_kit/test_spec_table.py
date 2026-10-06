"""`RowTableModel` + `SpecTable`: a table declared by its column specs and
shown the one way every table of the application is (`EPIC-033N`)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import ClassVar

import pytest
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QAbstractItemView
from Sagittarius_Elite_Warrior.src.support.ui_kit.i_symbol_precisions import (
    ISymbolPrecisions,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    PRECISION_ROLE,
    ColumnKind,
    ColumnSpec,
    DisplayValue,
    Precision,
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


@dataclass(frozen=True)
class _Stamp:
    name: str
    at: datetime | None


class _StampsModel(RowTableModel[_Stamp]):
    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("name", "Name", ColumnKind.TEXT, stretch=True),
        ColumnSpec("at", "At", ColumnKind.TIMESTAMP),
    )

    def _value(self, row: _Stamp, column: int) -> DisplayValue:
        return (row.name, row.at)[column]


def test_a_timestamp_column_sorts_by_time_and_still_reads_as_a_timestamp(qapp):
    """Review of PR #351: Qt's own proxy cannot order a Python `datetime`, so
    a timestamp column did not sort at all. The Engine's `SpecProxyModel`
    orders the raw moment, so the cell holds the `datetime` itself."""
    table = SpecTable(_StampsModel(), object_name="tblStamps", empty_text="None.")
    first = datetime(2026, 1, 6, tzinfo=UTC)
    table.model.set_rows(
        [
            _Stamp("c", first),
            # A naive moment reads as UTC, this application's convention.
            _Stamp("a", datetime(2026, 1, 2, tzinfo=UTC).replace(tzinfo=None)),
            _Stamp("e", None),
            _Stamp("d", datetime(2026, 1, 10, tzinfo=UTC)),
            _Stamp("b", datetime(2026, 1, 4, tzinfo=UTC)),
        ]
    )
    assert table.model.data(table.model.index(0, 1)) == first

    table.view.sortByColumn(1, Qt.SortOrder.AscendingOrder)
    ascending = [table.text(row, 0) for row in range(5)]
    table.view.sortByColumn(1, Qt.SortOrder.DescendingOrder)
    descending = [table.text(row, 0) for row in range(5)]

    assert ascending == ["a", "b", "c", "d", "e"]
    # Qt reverses the whole order: the unknown moment comes first descending.
    assert descending == ["e", "d", "c", "b", "a"]
    table.view.sortByColumn(1, Qt.SortOrder.AscendingOrder)
    assert table.text(0, 1) == "2026-01-02 00:00:00"
    assert table.text(4, 1) == ""


@dataclass(frozen=True)
class _Order:
    symbol: str
    price: float
    quantity: float
    leverage: float


class _OrdersModel(RowTableModel[_Order]):
    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("symbol", "Symbol", ColumnKind.TEXT, stretch=True),
        ColumnSpec("price", "Price", ColumnKind.PRICE),
        ColumnSpec("quantity", "Quantity", ColumnKind.QUANTITY),
        ColumnSpec("leverage", "Leverage (x)", ColumnKind.QUANTITY),
    )
    SYMBOL_QUOTED: ClassVar[frozenset[str]] = frozenset({"price", "quantity"})

    def _value(self, row: _Order, column: int) -> DisplayValue:
        return (row.symbol, row.price, row.quantity, row.leverage)[column]

    def _symbol(self, row: _Order) -> str | None:
        return row.symbol


class _Filters(ISymbolPrecisions):
    """BTCUSDT's tick and step; every other symbol unknown until added."""

    def __init__(self) -> None:
        self.known: dict[str, tuple[str, str]] = {"BTCUSDT": ("0.1", "0.001")}

    def tick(self, symbol: str) -> Precision | None:
        known = self.known.get(symbol)
        return None if known is None else Precision(Decimal(known[0]))

    def step(self, symbol: str) -> Precision | None:
        known = self.known.get(symbol)
        return None if known is None else Precision(Decimal(known[1]))


def _orders_table() -> SpecTable[_Order]:
    table = SpecTable(_OrdersModel(), object_name="tblOrders", empty_text="None.")
    table.model.set_rows(
        [
            _Order("BTCUSDT", 64250.12, 0.0153, 10.0),
            _Order("NEWUSDT", 64250.12, 0.0153, 10.0),
        ]
    )
    return table


def test_a_quoted_cell_is_written_in_its_symbols_tick_and_step(qapp):
    table = _orders_table()
    table.model.use_precisions(_Filters())

    assert table.text(0, 1) == "64,250.1"
    assert table.text(0, 2) == "0.015"


def test_a_column_not_quoted_in_the_symbol_keeps_the_magnitude_rule(qapp):
    """A leverage is a quantity, but not of the symbol: the symbol's step is
    no leverage's precision."""
    table = _orders_table()
    table.model.use_precisions(_Filters())

    assert table.model.data(table.model.index(0, 3), PRECISION_ROLE) is None
    assert table.text(0, 3) == "10"


def test_a_symbol_whose_filters_are_unknown_keeps_the_magnitude_rule(qapp):
    table = _orders_table()
    table.model.use_precisions(_Filters())

    assert table.text(1, 1) == "64,250.12"
    assert table.text(1, 2) == "0.0153"


def test_a_table_given_no_filters_keeps_the_magnitude_rule(qapp):
    table = _orders_table()

    assert table.model.data(table.model.index(0, 1), PRECISION_ROLE) is None
    assert table.text(0, 1) == "64,250.12"


def test_filters_that_become_known_rewrite_the_cells(qapp):
    """A catalog fetched while the table is shown: the model says every
    cell changed, so the view writes them again."""
    table = _orders_table()
    filters = _Filters()
    table.model.use_precisions(filters)
    changed: list[object] = []
    table.model.dataChanged.connect(lambda *args: changed.append(args))

    filters.known["NEWUSDT"] = ("1", "1")
    table.model.refresh_precisions()

    assert changed
    assert table.text(1, 1) == "64,250"


@dataclass(frozen=True)
class _Lot:
    name: str
    size: Decimal | None


class _LotsModel(RowTableModel[_Lot]):
    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("name", "Name", ColumnKind.TEXT, stretch=True),
        ColumnSpec("size", "Size", ColumnKind.QUANTITY),
    )

    def _value(self, row: _Lot, column: int) -> DisplayValue:
        return (row.name, row.size)[column]


def test_a_decimal_column_holds_the_decimal_and_sorts_by_value(qapp):
    """A `Decimal` reaches the cell exactly, never through a float, and sorts
    as a number: `10` after `9.5`, which text would put first."""
    table = SpecTable(_LotsModel(), object_name="tblLots", empty_text="None.")
    table.model.set_rows(
        [
            _Lot("c", Decimal(10)),
            _Lot("a", Decimal("-0.1")),
            _Lot("d", None),
            _Lot("b", Decimal("9.5")),
        ]
    )

    table.sort_by(_LotsModel.column("size"))

    assert [table.text(row, 0) for row in range(4)] == ["a", "b", "c", "d"]
    held = table.model.data(table.model.index(0, 1))
    assert isinstance(held, Decimal)
    assert held == Decimal(10)
