"""`configure_spec_view` — the Engine's `configure_item_view`, plus the two
width rules a narrow panel needs (`EPIC-033N`, `ui-presentation-rule.md` §9).

The Engine gives a spec's `stretch` column Qt's `QHeaderView.Stretch` mode.
Qt sizes such a column to whatever the viewport leaves after the others, and
in a panel narrower than the columns that is nothing: the column falls to
the header's minimum section size and reads "Sym" over "BN…", while the
columns after it run off the right edge. A docked table is often that
narrow, so the Market Watchlist showed it at every window size.

Here the Engine is handed the specs with no column stretching, so every
column is an ordinary content-sized `Interactive` one, and this module
widens the spec's stretch column to fill the viewport, never narrowing it
below its content. A table wider than its panel then scrolls horizontally
with every column whole, which is what the rule asks for. The policy
belongs in the Engine's `_configure_header`; it lives here until an Engine
change is agreed.

And a scroll area's default size hint ignores what it holds, so the dock
around a table asked for a fixed 256 px whatever its columns. The view
adjusts its size hint to its contents when first shown, so a dock opens
wide enough for the columns it was given, within Qt's cap of 36 lines.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from PySide6.QtCore import QAbstractItemModel, QEvent, QObject
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QHeaderView,
    QTableView,
    QTreeView,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnSpec,
    IValueFormatter,
    Selection,
    SpecProxyModel,
    configure_item_view,
)


def configure_spec_view(
    view: QTableView | QTreeView,
    model: QAbstractItemModel,
    specs: Sequence[ColumnSpec],
    *,
    formatter: IValueFormatter | None = None,
    selection: Selection = Selection.SINGLE,
) -> SpecProxyModel:
    """Shows `model` in `view` as `configure_item_view` does, with the
    stretch column filling the view but never narrower than its content."""
    content_sized = [replace(spec, stretch=False) for spec in specs]
    proxy = configure_item_view(
        view, model, content_sized, formatter=formatter, selection=selection
    )
    view.setSizeAdjustPolicy(
        QAbstractScrollArea.SizeAdjustPolicy.AdjustToContentsOnFirstShow
    )
    for column, spec in enumerate(specs):
        if spec.stretch:
            StretchWithoutSqueezing(view, column)
    return proxy


def header_of(view: QTableView | QTreeView) -> QHeaderView:
    return view.horizontalHeader() if isinstance(view, QTableView) else view.header()


def content_width(view: QTableView | QTreeView, column: int) -> int:
    """The width `column` needs to show its title and its visible cells whole."""
    header = header_of(view)
    return max(header.sectionSizeHint(column), view.sizeHintForColumn(column))


class StretchWithoutSqueezing(QObject):
    """Gives `column` the width the other columns leave in the viewport, but
    never less than its content."""

    def __init__(self, view: QTableView | QTreeView, column: int) -> None:
        super().__init__(view)
        self._view = view
        self._column = column
        header_of(view).sectionResized.connect(self._on_section_resized)
        view.viewport().installEventFilter(self)
        proxy = view.model()
        proxy.modelReset.connect(self.fill)
        proxy.rowsInserted.connect(self.fill)
        self.fill()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.fill()
        return False

    def _on_section_resized(self, column: int, _old: int, _new: int) -> None:
        if column != self._column:
            self.fill()

    def fill(self) -> None:
        """Content width while the view is hidden: a hidden viewport's size
        is Qt's placeholder, and the size hint, taken before the first show,
        would grow the dock to fit it."""
        header = header_of(self._view)
        width = content_width(self._view, self._column)
        if self._view.isVisible():
            others = header.length() - header.sectionSize(self._column)
            width = max(width, self._view.viewport().width() - others)
        header.resizeSection(self._column, width)
