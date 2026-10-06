"""The text-fit checks of the workbench conformance suite (`EPIC-033N`):
what a table or a drop-down list shows is shown whole at each window size.

Like `workbench_widget_checks.py`, each answers the problems it found, one
line each, for `test_workbench_conformance.py` to ratchet. They measure what
the 2026-10-06 pictures showed by eye: the Market Watchlist's columns cut to
"Sym" and "BN…" or pushed past the dock's edge, and the Backtest Run setup's
time zone cut off mid-word.
"""

from __future__ import annotations

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


def column_problems(_window: QWidget, page: QWidget) -> list[str]:
    """§9: a visible table opens showing every column whole: no column
    narrower than its title and the cells it shows (Qt elides it), and no
    column beyond the right edge of the view (MS `ctrl-list-views`)."""
    found = []
    for view in page.findChildren(QTableView) + page.findChildren(QTreeView):
        if not view.isVisible():
            continue
        header = _header(view)
        name = f"{type(view).__name__} {view.objectName()!r}"
        for column in range(header.count()):
            if header.isSectionHidden(column):
                continue
            title = str(header.model().headerData(column, header.orientation()))
            need = max(header.sectionSizeHint(column), view.sizeHintForColumn(column))
            if header.sectionSize(column) < need:
                found.append(
                    f"{name}: column {title!r} is {header.sectionSize(column)} px, "
                    f"its content {need} px"
                )
            elif (
                header.sectionViewportPosition(column) + need > view.viewport().width()
            ):
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
