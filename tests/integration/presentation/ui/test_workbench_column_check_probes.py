"""Probes for the conformance suite's column checks (`EPIC-033N`): each
check, run on a hand-built table configured from its specs the way every
table of the app is, passes it as built, and sees the fault it exists to
catch once a delegate or a model overrides what the kind decides.

Retire when: the checks they probe are retired with the conformance suite.
"""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import QIdentityProxyModel, QModelIndex, QObject, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_column_checks import (
    alignment_problems,
    column_specs,
    digit_font_problems,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
    configure_item_view,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.configure_item_view import (
    CONFIGURED_PROPERTY,
)

_ROW: tuple[DisplayValue, ...] = ("BTCUSDT", 64250.1, 0.015, 3.5)


class _Quotes(RowTableModel[tuple[DisplayValue, ...]]):
    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("symbol", "Symbol", ColumnKind.TEXT, stretch=True),
        ColumnSpec("price", "Last price", ColumnKind.PRICE),
        ColumnSpec("volume", "Volume", ColumnKind.QUANTITY),
        ColumnSpec("change", "Change", ColumnKind.PERCENT),
    )

    def _value(self, row: tuple[DisplayValue, ...], column: int) -> DisplayValue:
        return row[column]


class _LeftEverywhere(QStyledItemDelegate):
    """A delegate that writes every cell left-aligned, whatever its kind."""

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex) -> None:  # noqa: N802 - Qt override
        super().initStyleOption(option, index)
        option.displayAlignment = Qt.AlignmentFlag.AlignLeft  # type: ignore[attr-defined]


class _LeftHeaders(QIdentityProxyModel):
    """A model over the specs' proxy that serves every title left-aligned."""

    def headerData(  # noqa: N802 - Qt override
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignLeft
        return super().headerData(section, orientation, role)


class _OwnFont(QStyledItemDelegate):
    """A delegate that writes every cell in a font of its own."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._font = QFont()
        self._font.setFamily("Serif")

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex) -> None:  # noqa: N802 - Qt override
        super().initStyleOption(option, index)
        option.font = self._font  # type: ignore[attr-defined]


def _page(qtbot, rows: int = 1) -> tuple[QWidget, QTableView]:
    page = QWidget()
    qtbot.addWidget(page)
    model = _Quotes(page)
    model.set_rows([_ROW] * rows)
    table = SpecTable(model, object_name="tblProbe", empty_text="Nothing")
    QVBoxLayout(page).addWidget(table.body)
    page.resize(600, 200)
    page.show()
    return page, table.view


def test_a_table_as_its_specs_configure_it_passes(qtbot) -> None:
    page, view = _page(qtbot)

    assert [spec.key for spec in column_specs(view) or ()] == [
        "symbol",
        "price",
        "volume",
        "change",
    ]
    assert alignment_problems(page, page) == []
    assert digit_font_problems(page, page) == []


def test_a_delegate_that_overrides_the_alignment_is_seen(qtbot) -> None:
    page, view = _page(qtbot)
    view.setItemDelegate(_LeftEverywhere(view))

    found = alignment_problems(page, page)

    assert found == [
        "QTableView 'tblProbe': column 'Last price' (price) is left-aligned, not right",
        "QTableView 'tblProbe': column 'Volume' (quantity) is left-aligned, not right",
        "QTableView 'tblProbe': column 'Change' (percent) is left-aligned, not right",
    ]


def test_a_model_that_overrides_the_alignment_is_seen(qtbot) -> None:
    page, view = _page(qtbot)
    over = _LeftHeaders(view)
    over.setSourceModel(view.model())
    view.setModel(over)

    found = alignment_problems(page, page)

    assert (
        "QTableView 'tblProbe': header 'Last price' (price) is left-aligned, not right"
        in found
    )
    assert not any("'Symbol'" in problem for problem in found)


def test_an_empty_table_is_judged_by_its_header(qtbot) -> None:
    """A table built bare (no empty-state page over it) shows its header with
    no rows: the header is judged and no cell is measured."""
    page = QWidget()
    qtbot.addWidget(page)
    view = QTableView(page)
    view.setObjectName("tblEmpty")
    configure_item_view(view, _Quotes(view), _Quotes.COLUMNS)
    over = _LeftHeaders(view)
    over.setSourceModel(view.model())
    view.setModel(over)
    QVBoxLayout(page).addWidget(view)
    page.show()

    assert len(alignment_problems(page, page)) == 3
    assert digit_font_problems(page, page) == []


def test_a_delegate_that_overrides_the_font_is_seen(qtbot) -> None:
    page, view = _page(qtbot)
    view.setItemDelegate(_OwnFont(view))

    found = digit_font_problems(page, page)

    assert len(found) == 4
    assert found[1].startswith(
        "QTableView 'tblProbe': column 'Last price' (price) is in"
    )


def test_a_configured_view_whose_kinds_cannot_be_read_is_seen(qtbot) -> None:
    page, view = _page(qtbot)
    bare = QTableView(page)
    bare.setObjectName("tblBare")
    bare.setModel(view.model().sourceModel())
    bare.setProperty(CONFIGURED_PROPERTY, True)
    page.layout().addWidget(bare)
    bare.show()

    assert alignment_problems(page, page) == [
        "QTableView 'tblBare': its column kinds cannot be read"
    ]
