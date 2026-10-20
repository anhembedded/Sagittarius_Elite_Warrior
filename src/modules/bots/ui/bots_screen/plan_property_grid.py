"""`BOT-206` — the Plan dock's figures as a property table: a heading per group, a row per property.

A `QTreeView` over a `QStandardItemModel`, configured the one way every table is
(`configure_item_view`, `ui-presentation-rule.md` §9). Two columns: the property, left, and its
value. A value reads by the kind of its row (`PropertyRow.kind`): a word (a venue, a symbol, a step's
state) left, a figure (a price, an amount, a duration) right and, where its digits line up, in the
platform's fixed-pitch font. The Engine aligns by the column's kind, so `RowKindDelegate` is its
delegate with the alignment of the row's kind; the column itself is declared `QUANTITY`, which is
what the first row (a heading, holding no value) shows the conformance checks. The formatter
writes a string "as given", so every sentence the screen's words built (`bot_facts.py`,
`bot_ladder_facts.py`) reaches the cell untouched.

Text wraps in its cell, which `QTreeView` paints but never makes room for (it sizes a row from one
line), so each row's height is asked of the wrapped text at the column's width (`SizeHintRole`) and
asked again whenever a column, a text or a row changes. Both columns share the width equally (the last stretches, the first is held at half).

The order of a property list is its meaning, so the table does not sort. A heading collapses; the
model is built once and only its texts and visibility change, so a collapsed group stays collapsed
while the figures refresh. The panel scrolls once, at the panel (`ui-presentation-rule.md` §3): the
tree has no scroll bar of its own and is as tall as its visible rows.

Copy: Ctrl+C on the focused table puts the selected rows on the clipboard, one `property⇥value` line
each, a selected heading with its visible rows. It is the list view's own standard command, not a
command of the application, so it has no menu entry.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import (
    QGuiApplication,
    QKeySequence,
    QShortcut,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QSizePolicy,
    QStyle,
    QTreeView,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_property_rows import (
    PropertyGroup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.row_kind_delegate import (
    ROW_KIND_ROLE,
    RowKindDelegate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.wrapped_rows import (
    wrapped_line_count,
    wrapped_row_size,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kind_font import kind_font
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import displayed_text_at
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    APP_VALUE_FORMATTER,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
    IValueFormatter,
    Selection,
    SpecProxyModel,
    configure_item_view,
)

PROPERTY_COLUMN, VALUE_COLUMN = 0, 1
#: The Value column is `QUANTITY` for the alignment and the digits' font its kind decides.
COLUMNS = (
    ColumnSpec("property", "Property", ColumnKind.TEXT),
    ColumnSpec("value", "Value", ColumnKind.QUANTITY),
)
#: A line of copied text: the property, a tab, its value.
COPY_SEPARATOR = "\t"


class PlanPropertyGrid:
    """@brief The property table of one bot: groups of rows whose values the panel writes by key."""

    def __init__(
        self,
        groups: Sequence[PropertyGroup],
        formatter: IValueFormatter = APP_VALUE_FORMATTER,
    ) -> None:
        self.model = QStandardItemModel(0, len(COLUMNS))
        self.view = QTreeView()
        self.view.setObjectName("tvBotProperties")
        self._groups = {group.key: self._add_group(group) for group in groups}
        self._rows = {
            row.key: (group.key, index)
            for group in groups
            for index, row in enumerate(group.rows)
        }
        self._row_count = {group.key: len(group.rows) for group in groups}
        self._off_rows: set[str] = set()
        self._off_groups: set[str] = set()
        self.proxy: SpecProxyModel = configure_item_view(
            self.view,
            self.model,
            COLUMNS,
            formatter=formatter,
            selection=Selection.EXTENDED,
            sortable=False,
        )
        self.view.setItemDelegate(RowKindDelegate(COLUMNS, formatter, self.view))
        self._set_up_view()
        copy = QShortcut(QKeySequence.StandardKey.Copy, self.view)
        copy.setContext(Qt.ShortcutContext.WidgetShortcut)
        copy.activated.connect(self.copy_selection)

    # -- building -------------------------------------------------------- #

    def _add_group(self, group: PropertyGroup) -> QStandardItem:
        heading = QStandardItem(group.title)
        heading.setEditable(False)
        font = heading.font()
        font.setBold(True)
        heading.setFont(font)
        value = QStandardItem()
        value.setEditable(False)
        # The heading's own value cell holds nothing; it is the column's kind, as the checks read it.
        column_digits = kind_font(COLUMNS[VALUE_COLUMN].kind)
        if column_digits is not None:
            value.setFont(column_digits)
        for row in group.rows:
            label, shown = QStandardItem(row.title), QStandardItem()
            for item in (label, shown):
                item.setEditable(False)
            shown.setData(row.kind, ROW_KIND_ROLE)
            digits = kind_font(row.kind)
            if digits is not None:
                shown.setFont(digits)
            label.setToolTip(row.title)
            heading.appendRow([label, shown])
        self.model.appendRow([heading, value])
        return heading

    def _set_up_view(self) -> None:
        view = self.view
        # The groups collapse, so the arrows and the indent come back after the
        # engine's flat-table setting.
        view.setRootIsDecorated(True)
        view.setWordWrap(True)
        view.setUniformRowHeights(False)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        # A scroll area's child is `Expanding` with a tiny minimum, so a panel shorter than the
        # table would squeeze it (70 px of 429 at 1024×700) and the table would scroll by itself.
        # `Minimum` makes its size hint the least height it gets, and the panel scrolls once.
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        header = view.header()
        # The engine's header mode stays (item views are configured by their specs, never per view);
        # the last column takes what the first leaves, and the first is held at half.
        header.setStretchLastSection(True)
        header.sectionResized.connect(self._on_section_resized)
        for row in range(self.proxy.rowCount()):
            view.setFirstColumnSpanned(row, QModelIndex(), True)
        view.expandAll()

    @property
    def body(self) -> QWidget:
        return self.view

    # -- the values ------------------------------------------------------ #

    def set_values(self, values: Mapping[str, DisplayValue]) -> None:
        """Writes the given values; keys left out keep their text.
        @raise KeyError a key that is no row of the table."""
        unknown = sorted(set(values) - set(self._rows))
        if unknown:
            raise KeyError(f"no property row for {unknown}")
        for key, raw in values.items():
            self._value_item(key).setData(raw, Qt.ItemDataRole.DisplayRole)
        self._fit_rows()

    def shown_value(self, key: str) -> str:
        """The text the table shows for `key`, formatter and all."""
        return displayed_text_at(self.view, self._proxy_index(key, VALUE_COLUMN))

    def shown_title(self, key: str) -> str:
        return displayed_text_at(self.view, self._proxy_index(key, PROPERTY_COLUMN))

    def row_keys(self) -> tuple[str, ...]:
        """Every row key, in the order the table lists them."""
        return tuple(self._rows)

    def _value_item(self, key: str) -> QStandardItem:
        group_key, index = self._rows[key]
        item = self._groups[group_key].child(index, VALUE_COLUMN)
        if item is None:
            raise LookupError(f"property row {key!r} has no value cell")
        return item

    # -- what is shown --------------------------------------------------- #

    def set_rows_shown(self, keys: Sequence[str], shown: bool) -> None:
        """Shows or hides rows by key; a group with no row to show is hidden with them."""
        for key in keys:
            if key not in self._rows:
                raise KeyError(f"no property row {key!r}")
            (self._off_rows.discard if shown else self._off_rows.add)(key)
        self._apply({self._rows[key][0] for key in keys})

    def set_group_shown(self, group_key: str, shown: bool) -> None:
        """Shows or hides a whole group. @raise KeyError a key that is no group."""
        if group_key not in self._groups:
            raise KeyError(f"no property group {group_key!r}")
        (self._off_groups.discard if shown else self._off_groups.add)(group_key)
        self._apply({group_key})

    def row_is_shown(self, key: str) -> bool:
        """Whether the row is on the table: not hidden, in a group that is not hidden either (a
        collapsed group still has its rows)."""
        group_key, index = self._rows[key]
        return self.group_is_shown(group_key) and not self.view.isRowHidden(
            index, self._group_index(group_key)
        )

    def group_is_shown(self, group_key: str) -> bool:
        return not self.view.isRowHidden(
            self._group_index(group_key).row(), QModelIndex()
        )

    def _apply(self, group_keys: set[str]) -> None:
        for group_key in group_keys:
            group_index = self._group_index(group_key)
            hidden_rows = 0
            for key, (owner, index) in self._rows.items():
                if owner != group_key:
                    continue
                off = key in self._off_rows
                hidden_rows += off
                self.view.setRowHidden(index, group_index, off)
            nothing_to_show = hidden_rows == self._row_count[group_key]
            self.view.setRowHidden(
                group_index.row(),
                QModelIndex(),
                group_key in self._off_groups or nothing_to_show,
            )
        self.view.updateGeometry()

    # -- columns and row heights ----------------------------------------- #

    def _on_section_resized(self) -> None:
        """Both columns share the width equally, whoever moved a divider or measured the content,
        and the rows are measured again at the new widths."""
        header = self.view.header()
        half = header.width() // len(COLUMNS)
        if half > 0 and header.sectionSize(PROPERTY_COLUMN) != half:
            header.resizeSection(PROPERTY_COLUMN, half)
        self._fit_rows()

    def _fit_rows(self) -> None:
        """Gives each row the height of its text wrapped to its column; a row of one line keeps
        the style's own height."""
        view, header = self.view, self.view.header()
        indent = view.indentation() * 2
        pad = 2 * (
            view.style().pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin) + 1
        )
        for key, (group_key, index) in self._rows.items():
            group = self._groups[group_key]
            lines = 1
            for column, taken in ((PROPERTY_COLUMN, indent), (VALUE_COLUMN, 0)):
                item = group.child(index, column)
                if item is None:
                    continue
                width = max(header.sectionSize(column) - taken - pad, 1)
                text = displayed_text_at(view, self._proxy_index(key, column))
                lines = max(lines, wrapped_line_count(item.font(), text, width))
            self._set_lines(key, lines)
        view.updateGeometry()

    def _set_lines(self, key: str, lines: int) -> None:
        group_key, index = self._rows[key]
        size = wrapped_row_size(self.view, lines) if lines > 1 else None
        for column in range(len(COLUMNS)):
            item = self._groups[group_key].child(index, column)
            if item is not None and item.data(Qt.ItemDataRole.SizeHintRole) != size:
                item.setData(size, Qt.ItemDataRole.SizeHintRole)

    def _group_index(self, group_key: str) -> QModelIndex:
        item = self._groups[group_key]
        return self.proxy.mapFromSource(self.model.indexFromItem(item))

    def _proxy_index(self, key: str, column: int) -> QModelIndex:
        group_key, index = self._rows[key]
        parent = self.model.indexFromItem(self._groups[group_key])
        source = self.model.index(index, column, parent)
        return self.proxy.mapFromSource(source)

    # -- copy ------------------------------------------------------------ #

    def copy_text(self) -> str:
        """The selected rows as lines of `property⇥value`; a selected heading brings its visible rows."""
        lines: list[str] = []
        taken: set[tuple[int, int]] = set()
        for selected in sorted(
            self.view.selectionModel().selectedRows(),
            key=lambda index: (index.parent().row(), index.row()),
        ):
            lines.extend(self._lines_of(selected, taken))
        return "\n".join(lines)

    def _lines_of(self, index: QModelIndex, taken: set[tuple[int, int]]) -> list[str]:
        if index.parent().isValid():
            return self._line(index, taken)
        lines = self._line(index, taken)
        for child in range(self.proxy.rowCount(index)):
            if not self.view.isRowHidden(child, index):
                lines.extend(self._line(self.proxy.index(child, 0, index), taken))
        return lines

    def _line(self, index: QModelIndex, taken: set[tuple[int, int]]) -> list[str]:
        place = (index.parent().row(), index.row())
        if place in taken:
            return []
        taken.add(place)
        title = displayed_text_at(self.view, index.siblingAtColumn(PROPERTY_COLUMN))
        value = displayed_text_at(self.view, index.siblingAtColumn(VALUE_COLUMN))
        return [f"{title}{COPY_SEPARATOR}{value}" if value else title]

    def copy_selection(self) -> None:
        text = self.copy_text()
        if text:
            QGuiApplication.clipboard().setText(text)
