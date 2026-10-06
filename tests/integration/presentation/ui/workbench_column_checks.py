"""The column checks of the workbench conformance suite (`EPIC-033N`): what
each visible column shows agrees with its kind.

`item_view_conventions` proves a view was configured from its column specs;
these read what the view then shows, cell by cell, through the view's own
model and delegate, so a delegate or a model that overrides the kind's
presentation is caught where a person would see it:

· `alignment_problems` — numbers, money and durations right; text,
  identifiers, sides, states and dates left (`ui-presentation-rule.md` §9,
  MS `ctrl-list-views`), in the header and in the first row;
· `digit_font_problems` — a price, a quantity and money in the platform's
  fixed-pitch font, every other kind in the application font (decision D6).

A column's kind is read from the specs the view was configured with (the
Engine's `SpecProxyModel`, wherever it sits in the view's chain of proxies);
a configured view whose kinds cannot be read is itself a problem. The
expectations are written here, not read from the Engine's `ColumnKind`, so
a kind whose own alignment drifted would fail too. A cell is measured only
where a row exists; a view with no rows is judged by its header, and a
`SpecTable` with no rows shows its empty-state page instead, which is not a
column at all.
"""

from __future__ import annotations

from PySide6.QtCore import QAbstractItemModel, QAbstractProxyModel, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QHeaderView,
    QStyleOptionViewItem,
    QTableView,
    QTreeView,
    QWidget,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    SpecProxyModel,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.configure_item_view import (
    CONFIGURED_PROPERTY,
)

#: Right-aligned: the kinds whose value is a number (MS `ctrl-list-views`).
_RIGHT_KINDS = frozenset(
    {
        ColumnKind.QUANTITY,
        ColumnKind.PRICE,
        ColumnKind.PERCENT,
        ColumnKind.MONEY,
        ColumnKind.DURATION,
    }
)
#: Fixed-pitch: the kinds whose digits line up down a column (D6).
_DIGIT_KINDS = frozenset({ColumnKind.PRICE, ColumnKind.QUANTITY, ColumnKind.MONEY})
_HORIZONTAL = Qt.AlignmentFlag.AlignHorizontal_Mask
_RIGHT = Qt.AlignmentFlag.AlignRight
_LEFT = Qt.AlignmentFlag.AlignLeft


def _views(page: QWidget) -> list[QTableView | QTreeView]:
    views: list[QTableView | QTreeView] = [
        *page.findChildren(QTableView),
        *page.findChildren(QTreeView),
    ]
    return [view for view in views if view.isVisible()]


def _name(view: QTableView | QTreeView) -> str:
    return f"{type(view).__name__} {view.objectName()!r}"


def _header(view: QTableView | QTreeView) -> QHeaderView:
    return view.horizontalHeader() if isinstance(view, QTableView) else view.header()


def column_specs(view: QTableView | QTreeView) -> tuple[ColumnSpec, ...] | None:
    """The specs the view was configured with, from the `SpecProxyModel` in
    its chain of models; `None` when there is none."""
    model: QAbstractItemModel | None = view.model()
    while model is not None:
        if isinstance(model, SpecProxyModel):
            return model.specs
        model = model.sourceModel() if isinstance(model, QAbstractProxyModel) else None
    return None


def _cell(view: QTableView | QTreeView, column: int) -> QStyleOptionViewItem | None:
    """The first row's cell in `column` as the view's delegate paints it."""
    model = view.model()
    if model.rowCount() == 0:
        return None
    index = model.index(0, column)
    option = QStyleOptionViewItem()
    view.itemDelegateForIndex(index).initStyleOption(option, index)
    return option


def _side(alignment: object) -> str:
    flags = Qt.AlignmentFlag(int(alignment or 0)) & _HORIZONTAL
    if flags & _RIGHT:
        return "right"
    return "left" if flags in (_LEFT, Qt.AlignmentFlag(0)) else str(flags)


def _expected_side(kind: ColumnKind) -> str:
    return "right" if kind in _RIGHT_KINDS else "left"


def _shown_columns(
    view: QTableView | QTreeView, found: list[str]
) -> list[tuple[int, ColumnSpec]]:
    """Each visible column with its spec; a problem when the view's kinds
    cannot be read."""
    specs = column_specs(view)
    if specs is None:
        if view.property(CONFIGURED_PROPERTY):
            found.append(f"{_name(view)}: its column kinds cannot be read")
        return []
    header = _header(view)
    return [
        (column, spec)
        for column, spec in enumerate(specs)
        if column < header.count() and not header.isSectionHidden(column)
    ]


def alignment_problems(_window: QWidget, page: QWidget) -> list[str]:
    """§9: numbers, money and durations right; text, identifiers and dates
    left — in the header the view shows and in its first row."""
    found: list[str] = []
    for view in _views(page):
        for column, spec in _shown_columns(view, found):
            want = _expected_side(spec.kind)
            header = view.model().headerData(
                column, Qt.Orientation.Horizontal, Qt.ItemDataRole.TextAlignmentRole
            )
            if _side(header) != want:
                found.append(
                    f"{_name(view)}: header {spec.title!r} ({spec.kind.value}) is "
                    f"{_side(header)}-aligned, not {want}"
                )
            cell = _cell(view, column)
            if cell is not None and _side(cell.displayAlignment) != want:
                found.append(
                    f"{_name(view)}: column {spec.title!r} ({spec.kind.value}) "
                    f"is {_side(cell.displayAlignment)}-aligned, not {want}"
                )
    return found


def digit_font_problems(_window: QWidget, page: QWidget) -> list[str]:
    """D6: a price, a quantity and money in the platform's fixed-pitch font;
    every other kind in the application font."""
    fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
    general = QApplication.font().family()
    found: list[str] = []
    for view in _views(page):
        for column, spec in _shown_columns(view, found):
            cell = _cell(view, column)
            if cell is None:
                continue
            family = QFont(cell.font).family()
            want = fixed if spec.kind in _DIGIT_KINDS else general
            if family != want:
                found.append(
                    f"{_name(view)}: column {spec.title!r} ({spec.kind.value}) "
                    f"is in {family!r}, not {want!r}"
                )
    return found
