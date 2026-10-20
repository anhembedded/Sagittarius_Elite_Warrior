"""`BOT-209` — the Plan dock's checks: one row each, the ones that need attention first, the rest folded.

A `QTreeView` over a `QStandardItemModel`, configured the one way every table is
(`configure_item_view`, `ui-presentation-rule.md` §9), under one heading, "Checks", whose value says
how the plan stands ("1 blocking Start, 2 warnings"). A check is a row: the platform's stop sign or
warning icon, its title, and its headline; the whole sentence with its numbers is the row's tooltip
and accessible description, so a long explanation never lengthens the dock. The checks that passed
are one row, "14 checks passed", that opens to list them; whether it is open survives a re-judging
(a person opened it to look). Nothing to judge yet (the market is not read) hides the table.

Like the property table it is as tall as its rows and has no scroll bar of its own: the panel
scrolls once, at the panel (`ui-presentation-rule.md` §3).
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QIcon, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QSizePolicy,
    QStyle,
    QTreeView,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import VerdictSeverity
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_checks import (
    PlanCheck,
    PlanChecks,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.wrapped_rows import (
    wrapped_line_count,
    wrapped_row_size,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import displayed_text_at
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    Selection,
    SpecProxyModel,
    configure_item_view,
)

CHECK_COLUMN, FINDING_COLUMN = 0, 1
COLUMNS = (
    ColumnSpec("check", "Check", ColumnKind.TEXT),
    ColumnSpec("finding", "Finding", ColumnKind.TEXT),
)
HEADING = "Checks"
#: Marks the row the passed checks fold into.
_PASSED_ROW = Qt.ItemDataRole.UserRole + 2
#: The share of the width the title column takes; the findings are the longer text.
_TITLE_SHARE = 0.4

_ICONS = {
    VerdictSeverity.REFUSED: QStyle.StandardPixmap.SP_MessageBoxCritical,
    VerdictSeverity.WARNING: QStyle.StandardPixmap.SP_MessageBoxWarning,
    VerdictSeverity.OK: QStyle.StandardPixmap.SP_DialogApplyButton,
}


class PlanChecksView:
    """@brief The list of what the kind says about the plan on screen."""

    def __init__(self) -> None:
        self.model = QStandardItemModel(0, len(COLUMNS))
        self.view = QTreeView()
        self.view.setObjectName("tvBotChecks")
        self.proxy: SpecProxyModel = configure_item_view(
            self.view,
            self.model,
            COLUMNS,
            selection=Selection.EXTENDED,
            sortable=False,
        )
        self._passed_open = False
        self._set_up_view()
        self.view.expanded.connect(self._remember_passed_state)
        self.view.collapsed.connect(self._remember_passed_state)
        self.view.setVisible(False)

    @property
    def body(self) -> QWidget:
        return self.view

    def show_checks(self, checks: PlanChecks) -> None:
        """Replaces the rows; nothing to judge hides the list."""
        self.model.removeRows(0, self.model.rowCount())
        shown = bool(checks.everything)
        self.view.setVisible(shown)
        if not shown:
            return
        heading = self._add_heading(checks)
        for check in checks.attention:
            heading.appendRow(self._row(check))
        passed_row = self._add_passed(heading, checks)
        self.view.expand(self._proxy_of(heading))
        if passed_row is not None:
            index = self._proxy_of(passed_row)
            self.view.setFirstColumnSpanned(index.row(), index.parent(), True)
            self.view.setExpanded(index, self._passed_open)
        self._fit_rows()

    # -- what is shown, for a test and a screen reader ------------------- #

    def rows(self) -> tuple[tuple[str, str], ...]:
        """Every visible row as (title, finding), top to bottom; a folded group's rows are not visible."""
        found: list[tuple[str, str]] = []
        self._collect(QModelIndex(), found)
        return tuple(found)

    def tooltip_of(self, title: str) -> str:
        """The whole explanation of the row titled `title`; `""` when there is none."""
        index = self._find(QModelIndex(), title)
        return index.data(Qt.ItemDataRole.ToolTipRole) or "" if index else ""

    def passed_row_is_open(self) -> bool:
        return self._passed_open

    def open_passed(self, opened: bool) -> None:
        """Opens or folds the passed checks, as a click on their row would."""
        index = self._find_passed()
        if index is not None:
            self.view.setExpanded(index, opened)

    # -- building --------------------------------------------------------- #

    def _add_heading(self, checks: PlanChecks) -> QStandardItem:
        heading = QStandardItem(HEADING)
        font = heading.font()
        font.setBold(True)
        heading.setFont(font)
        value = QStandardItem(checks.tally)
        for item in (heading, value):
            item.setEditable(False)
        self.model.appendRow([heading, value])
        return heading

    def _add_passed(
        self, heading: QStandardItem, checks: PlanChecks
    ) -> QStandardItem | None:
        if not checks.passed:
            return None
        folded = QStandardItem(self._icon(VerdictSeverity.OK), checks.passed_text)
        folded.setData(True, _PASSED_ROW)
        folded.setEditable(False)
        quiet = QStandardItem()
        quiet.setEditable(False)
        for check in checks.passed:
            folded.appendRow(self._row(check, icon=False))
        heading.appendRow([folded, quiet])
        return folded

    def _row(self, check: PlanCheck, *, icon: bool = True) -> list[QStandardItem]:
        title = QStandardItem(check.title)
        if icon:
            title.setIcon(self._icon(check.severity))
        finding = QStandardItem(check.headline)
        for item in (title, finding):
            item.setEditable(False)
            item.setToolTip(check.detail)
            item.setData(check.detail, Qt.ItemDataRole.AccessibleDescriptionRole)
        return [title, finding]

    def _icon(self, severity: VerdictSeverity) -> QIcon:
        return self.view.style().standardIcon(_ICONS[severity])

    # -- the view --------------------------------------------------------- #

    def _set_up_view(self) -> None:
        view = self.view
        view.setRootIsDecorated(True)
        view.setWordWrap(True)
        view.setUniformRowHeights(False)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        header = view.header()
        header.setStretchLastSection(True)
        header.sectionResized.connect(self._on_section_resized)

    def _remember_passed_state(self, index: QModelIndex) -> None:
        if index.data(_PASSED_ROW):
            self._passed_open = self.view.isExpanded(index)
        self.view.updateGeometry()

    def _on_section_resized(self) -> None:
        """The title column keeps its share of the width, whoever moved a divider, and every row is
        measured again at the new widths."""
        header = self.view.header()
        title = int(header.width() * _TITLE_SHARE)
        if title > 0 and header.sectionSize(CHECK_COLUMN) != title:
            header.resizeSection(CHECK_COLUMN, title)
        self._fit_rows()

    def _fit_rows(self) -> None:
        """Gives each row the height of its text wrapped to its column."""
        self._fit_children(self.model.invisibleRootItem(), depth=0)
        self.view.updateGeometry()

    def _fit_children(self, parent: QStandardItem, depth: int) -> None:
        view, header = self.view, self.view.header()
        style = view.style()
        indent = view.indentation() * (depth + 1)
        icon_width = style.pixelMetric(QStyle.PixelMetric.PM_SmallIconSize) + 2 * (
            style.pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin) + 1
        )
        pad = 2 * (style.pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin) + 1)
        for row in range(parent.rowCount()):
            lines = 1
            for column in range(len(COLUMNS)):
                item = parent.child(row, column)
                if item is None or not item.text():
                    continue
                taken = indent if column == CHECK_COLUMN else 0
                icon = 0 if item.icon().isNull() else icon_width
                width = max(header.sectionSize(column) - taken - icon - pad, 1)
                lines = max(lines, wrapped_line_count(item.font(), item.text(), width))
            size = wrapped_row_size(view, lines) if lines > 1 else None
            for column in range(len(COLUMNS)):
                item = parent.child(row, column)
                if item is not None and item.data(Qt.ItemDataRole.SizeHintRole) != size:
                    item.setData(size, Qt.ItemDataRole.SizeHintRole)
            first = parent.child(row, CHECK_COLUMN)
            if first is not None and first.hasChildren():
                self._fit_children(first, depth + 1)

    # -- walking ---------------------------------------------------------- #

    def _proxy_of(self, item: QStandardItem) -> QModelIndex:
        return self.proxy.mapFromSource(self.model.indexFromItem(item))

    def _collect(self, parent: QModelIndex, found: list[tuple[str, str]]) -> None:
        for row in range(self.proxy.rowCount(parent)):
            index = self.proxy.index(row, CHECK_COLUMN, parent)
            found.append(
                (
                    displayed_text_at(self.view, index),
                    displayed_text_at(self.view, index.siblingAtColumn(FINDING_COLUMN)),
                )
            )
            if self.view.isExpanded(index):
                self._collect(index, found)

    def _find(self, parent: QModelIndex, title: str) -> QModelIndex | None:
        for row in range(self.proxy.rowCount(parent)):
            index = self.proxy.index(row, CHECK_COLUMN, parent)
            if displayed_text_at(self.view, index) == title:
                return index
            nested = self._find(index, title)
            if nested is not None:
                return nested
        return None

    def _find_passed(self) -> QModelIndex | None:
        heading = self.proxy.index(0, CHECK_COLUMN)
        for row in range(self.proxy.rowCount(heading)):
            index = self.proxy.index(row, CHECK_COLUMN, heading)
            if index.data(_PASSED_ROW):
                return index
        return None
