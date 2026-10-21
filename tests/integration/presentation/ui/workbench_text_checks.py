"""The text-fit checks of the workbench conformance suite (`EPIC-033N`):
what a table or a drop-down list shows is shown whole at each window size.

Like `workbench_widget_checks.py`, each answers the problems it found, one
line each, for `test_workbench_conformance.py` to ratchet. They measure what
the 2026-10-06 pictures showed by eye: the Market Watchlist's columns cut to
"Sym" and "BN…" or pushed past the dock's edge, and the Backtest Run setup's
time zone cut off mid-word.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHeaderView,
    QStyle,
    QStyleOptionComboBox,
    QTableView,
    QTreeView,
    QWidget,
)


def _header(view: QTableView | QTreeView) -> QHeaderView:
    return view.horizontalHeader() if isinstance(view, QTableView) else view.header()


def _wraps(view: QTableView | QTreeView) -> bool:
    """A tree that was switched to wrap its words shows a long text over more lines, which its
    owner sizes the rows for (the Plan's checks). A table says nothing by `wordWrap()`: it is on by
    default and its rows stay one line, so a cut cell is elided all the same."""
    return isinstance(view, QTreeView) and view.wordWrap()


def _scrolls_sideways(view: QTableView | QTreeView) -> bool:
    """A view narrower than its columns reaches the rest by its horizontal scroll bar, which
    §9 asks for (`BOT-128`): a column beyond the edge is a problem only where nothing scrolls."""
    return view.horizontalScrollBarPolicy() != Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def column_problems(_window: QWidget, page: QWidget) -> list[str]:
    """§9: a visible table opens showing every column whole: no column
    narrower than its title and the cells it shows (Qt elides it), and no
    column beyond the right edge of a view that does not scroll sideways
    (MS `ctrl-list-views`). A tree that wraps its words (the Plan's checks) shows a long text
    over more lines instead of eliding it, so its column may be narrower than the one line, but never than its title."""
    found = []
    for view in page.findChildren(QTableView) + page.findChildren(QTreeView):
        if not view.isVisible() or view.visibleRegion().isEmpty():
            # A panel tabbed behind another is not drawn: Qt parks it at its minimum width, and
            # it is measured when its tab is in front (`BUG-245`, as `combo_problems`).
            continue
        header = _header(view)
        name = f"{type(view).__name__} {view.objectName()!r}"
        for column in range(header.count()):
            if header.isSectionHidden(column):
                continue
            title = str(header.model().headerData(column, header.orientation()))
            # A wrapping tree puts a long cell over more lines, but a header title never wraps.
            floor = header.sectionSizeHint(column)
            need = floor if _wraps(view) else max(floor, view.sizeHintForColumn(column))
            if header.sectionSize(column) < need:
                found.append(
                    f"{name}: column {title!r} is {header.sectionSize(column)} px, "
                    f"its content {need} px"
                )
            elif header.sectionViewportPosition(column) + (
                header.sectionSize(column) if _wraps(view) else need
            ) > view.viewport().width() and not _scrolls_sideways(view):
                found.append(f"{name}: column {title!r} runs past the view's edge")
    return found


def combo_problems(_window: QWidget, page: QWidget) -> list[str]:
    """§3: a visible drop-down list shows its chosen item whole; the style,
    not a fixed width, decides how wide it is (Qt `QComboBox` elides it).
    A panel tabbed behind another is not drawn: Qt keeps it "visible" but
    parks it outside the window at its minimum width (`EPIC-033I`, the Trade
    mode's Strategy panel), and it is measured when its tab is in front."""
    found = []
    for combo in page.findChildren(QComboBox):
        if not combo.isVisible() or combo.isEditable() or not combo.currentText():
            continue
        if combo.visibleRegion().isEmpty():
            continue
        # Where the style paints the text, and so where Qt elides it.
        option = QStyleOptionComboBox()
        combo.initStyleOption(option)
        field = combo.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxEditField,
            combo,
        )
        need = combo.fontMetrics().horizontalAdvance(combo.currentText())
        if field.width() < need:
            found.append(
                f"QComboBox {combo.objectName()!r} shows {field.width()} px of "
                f"{combo.currentText()!r}, which needs {need} px"
            )
    return found
