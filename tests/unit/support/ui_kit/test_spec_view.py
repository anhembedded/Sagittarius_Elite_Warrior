"""`configure_spec_view`: a table's stretch column fills the view but never
squeezes below its content, and a narrow panel scrolls instead of dropping
columns (`EPIC-033N`, `ui-presentation-rule.md` §9)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import pytest
from PySide6.QtWidgets import QHeaderView, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_view import content_width
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)


@dataclass(frozen=True)
class _Quote:
    symbol: str
    price: float
    volume: float


class _QuotesModel(RowTableModel[_Quote]):
    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("symbol", "Symbol", ColumnKind.TEXT, stretch=True),
        ColumnSpec("price", "Last price", ColumnKind.PRICE),
        ColumnSpec("volume", "Volume", ColumnKind.QUANTITY),
    )

    def _value(self, row: _Quote, column: int) -> DisplayValue:
        return (row.symbol, row.price, row.volume)[column]


@dataclass
class _Shown:
    """The table and the panel holding it: the panel must outlive the test,
    or Python frees it and the view with it."""

    table: SpecTable[_Quote]
    panel: QWidget


def _shown(qtbot, width: int) -> _Shown:
    table = SpecTable(_QuotesModel(), object_name="tblQuotes", empty_text="None.")
    table.model.set_rows([_Quote("BNBUSDT", 600.5, 1200.0)])
    panel = QWidget()
    qtbot.addWidget(panel)
    QVBoxLayout(panel).addWidget(table.body)
    panel.resize(width, 240)
    panel.show()
    qtbot.waitExposed(panel)
    return _Shown(table, panel)


@pytest.mark.parametrize("width", [120, 900])
def test_the_stretch_column_never_shows_less_than_its_content(qtbot, width):
    """Qt's own `Stretch` mode gave the first column what the others left:
    nothing, in a narrow dock, so the Watchlist read "Sym" over "BN…"."""
    shown = _shown(qtbot, width)
    table = shown.table
    header = table.view.horizontalHeader()

    assert header.sectionSize(0) >= content_width(table.view, 0)
    assert header.sectionResizeMode(0) is QHeaderView.ResizeMode.Interactive


def test_a_view_leaving_the_stretch_column_too_little_keeps_it_whole(qtbot):
    """The Watchlist's case: the dock is a little wider than the columns
    after the first, so Qt's `Stretch` left the first a sliver of its own."""
    shown = _shown(qtbot, 900)
    view = shown.table.view
    others = content_width(view, 1) + content_width(view, 2)
    frame = shown.panel.width() - view.viewport().width()
    sliver = content_width(view, 0) // 3

    shown.panel.resize(frame + others + sliver, 240)
    qtbot.waitUntil(lambda: view.viewport().width() <= others + sliver)

    assert view.horizontalHeader().sectionSize(0) >= content_width(view, 0)


def test_a_wide_view_is_filled_by_the_stretch_column(qtbot):
    shown = _shown(qtbot, 900)
    table = shown.table
    view = table.view

    assert view.horizontalHeader().length() == view.viewport().width()
    assert view.horizontalHeader().sectionSize(0) > content_width(view, 0)


def test_a_narrow_view_scrolls_with_every_column_whole(qtbot):
    shown = _shown(qtbot, 120)
    table = shown.table
    view = table.view
    header = view.horizontalHeader()

    assert header.length() > view.viewport().width()
    assert view.horizontalScrollBar().maximum() > 0
    for column in range(header.count()):
        assert header.sectionSize(column) >= content_width(view, column)


def test_the_view_asks_for_the_width_of_its_columns(qtbot):
    """A dock opens at its content's size hint: a hint taken from the columns
    gives the Watchlist's dock room for all four of them."""
    table = SpecTable(_QuotesModel(), object_name="tblQuotes", empty_text="None.")
    # Wider than Qt's default hint for a scroll area, which ignores content.
    table.model.set_rows([_Quote("ETHUSDT_PERPETUAL_DELIVERY_250627", 600.5, 1.0)])
    view = table.view
    natural = sum(content_width(view, column) for column in range(3))

    assert view.sizeHint().width() >= natural
