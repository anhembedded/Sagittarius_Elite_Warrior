"""QtWidgets building blocks for DatabaseScreen (EPIC-005E), each a direct port of
one QML component this screen used: `TimeRangeCard`, `LogPanel`, `AppProgressBar`
(all from the engine kit or `components/`), and the `SymbolPickerModal`/
`ModalDialogCard` confirm-dialog pattern. Kept in their own module so
`data_management_view.py` stays about assembly, not primitive construction.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QScrollArea,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.date_range_picker import (
    pick_date_range,
)
from sagittarius_engine.extensions.pyside_mvc.widgets import (
    Banner,
    Column,
    DataRow,
    Overlay,
    RowAction,
    Severity,
    StyleRole,
    Tone,
    apply_role,
)

_FULL_COVERAGE_THRESHOLD = 99.0

if TYPE_CHECKING:
    from .data_management_view_model import DataManagementViewModel
    from .kline_inspector_table_model import KLineInspectorTableModel


class RowWidgetDelegate(QStyledItemDelegate):
    """Sizes a `QListView` item to the widget actually placed in it.

    `setIndexWidget()` does not tell the list how tall its widget is — the
    item keeps the delegate's default height, which is one line of text.
    Both of this screen's tables have been clipped to 14px since it was
    ported: enough for the labels, not for a row's action buttons, which is
    why those rendered as empty outlines with their text cut off
    (`BUG-051`).

    Reading the widget's own `sizeHint()` rather than naming a height keeps
    the two from drifting when a row gains a taller control.
    """

    def sizeHint(self, option, index):
        hint = super().sizeHint(option, index)
        view = self.parent()
        widget = view.indexWidget(index) if view is not None else None
        if widget is None:
            return hint
        hint.setHeight(max(hint.height(), widget.sizeHint().height()))
        return hint


def field_style(extra_height: int | None = None) -> str:
    """QSS matching `FieldBackground.qml`: STATE_IDLE_BG fill, BORDER outline,
    6px radius. `extra_height` overrides the default 32px min-height (the
    search box uses 26px, matching `FieldBackground { implicitHeight: 26 }`)."""
    height = extra_height if extra_height is not None else 32
    return (
        f"background-color: {Palette.STATE_IDLE_BG}; color: {Palette.TEXT_PRIMARY}; "
        f"border: 1px solid {Palette.BORDER}; border-radius: 6px; "
        f"min-height: {height}px; padding: 0 6px;"
    )


class TimeRangeCardWidget(QWidget):  # base-exempt: a form group, not a card
    """Port of the engine's `TimeRangeCard.qml`: a "use custom time range"
    toggle plus two free-text From/To fields (not QDateTimeEdit — the QML
    version never validated format at the widget level either; the
    presenter's `_parse_datetime`/`SyncCoordinator.parse_datetime` is the
    real validation, unchanged by this migration).

    **Named "Card" but not one**, and deliberately left that way: it is a
    checkbox stacked over two fields with zero margins and no chrome of its
    own. The name is inherited from the QML file it ports. Giving it
    `Panel`'s background and border to match the name would be styling
    driven by a filename."""

    customTimeToggled = Signal(bool)
    fromDateTimeEdited = Signal(str)
    toDateTimeEdited = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._read_only = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._toggle = QCheckBox("Use Custom Time Range")
        self._toggle.setStyleSheet(f"color: {Palette.TEXT_PRIMARY};")
        self._toggle.toggled.connect(self._on_toggled)
        layout.addWidget(self._toggle)

        self._from_field = QLineEdit()
        self._from_field.setObjectName("txtFromDateTime")
        self._from_field.setPlaceholderText("From  yyyy-MM-dd HH:mm")
        self._from_field.setStyleSheet(field_style())
        self._from_field.textEdited.connect(self.fromDateTimeEdited)
        layout.addWidget(self._from_field)

        self._to_field = QLineEdit()
        self._to_field.setObjectName("txtToDateTime")
        self._to_field.setPlaceholderText("To  yyyy-MM-dd HH:mm")
        self._to_field.setStyleSheet(field_style())
        self._to_field.textEdited.connect(self.toDateTimeEdited)
        layout.addWidget(self._to_field)

        # A second way to fill the same two fields, not a replacement for
        # them: the presenter parses what is typed, and a user who prefers
        # typing keeps that.
        pick_row = QHBoxLayout()
        pick_row.setContentsMargins(0, 0, 0, 0)
        pick_row.addStretch(1)
        self._btn_pick_range = QPushButton("Chọn lịch")
        self._btn_pick_range.setObjectName("btnPickDateRange")
        self._btn_pick_range.setFixedHeight(22)
        self._btn_pick_range.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_pick_range.setStyleSheet(
            f"QPushButton {{ color: {Palette.ACCENT}; background: transparent; "
            f"border: 0; border-radius: 4px; font-size: 11px; padding: 0 6px; }}"
            f"QPushButton:hover {{ background-color: {Palette.STATE_HOVER_BG}; }}"
        )
        self._btn_pick_range.clicked.connect(self._on_pick_range)
        pick_row.addWidget(self._btn_pick_range)
        layout.addLayout(pick_row)

        self._apply_enabled_state()

    def _on_pick_range(self) -> None:
        chosen = pick_date_range(
            self,
            start_text=self._from_field.text(),
            end_text=self._to_field.text(),
        )
        if chosen is None:
            return
        start, end = chosen
        self._from_field.setText(start)
        self._to_field.setText(end)
        # The same signals typing emits — the view model must not be able to
        # tell which of the two ways filled the field.
        self.fromDateTimeEdited.emit(start)
        self.toDateTimeEdited.emit(end)

    def _on_toggled(self, checked: bool) -> None:
        self._apply_enabled_state()
        self.customTimeToggled.emit(checked)

    def _apply_enabled_state(self) -> None:
        fields_enabled = self._toggle.isChecked() and not self._read_only
        self._from_field.setEnabled(fields_enabled)
        self._to_field.setEnabled(fields_enabled)
        self._btn_pick_range.setEnabled(fields_enabled)
        self._toggle.setEnabled(not self._read_only)

    def set_use_custom_time(self, value: bool) -> None:
        self._toggle.blockSignals(True)
        self._toggle.setChecked(value)
        self._toggle.blockSignals(False)
        self._apply_enabled_state()

    def set_read_only(self, value: bool) -> None:
        self._read_only = value
        self._apply_enabled_state()

    def set_from_date_time(self, value: str) -> None:
        if self._from_field.text() != value:
            self._from_field.setText(value)

    def set_to_date_time(self, value: str) -> None:
        if self._to_field.text() != value:
            self._to_field.setText(value)


#: The KLine table's columns — matches `KLineInspectorModal.qml`'s fixed
#: widths (140/80/80/80/80/105/75/70). One spec, read by both the heading
#: strip and every row.
_KLINE_COLUMNS = (
    Column("Thời gian (UTC)", 20),
    Column("Mở (Open)", 11, Qt.AlignmentFlag.AlignRight),
    Column("Cao (High)", 11, Qt.AlignmentFlag.AlignRight),
    Column("Thấp (Low)", 11, Qt.AlignmentFlag.AlignRight),
    Column("Đóng (Close)", 11, Qt.AlignmentFlag.AlignRight),
    Column("Khối lượng (Vol)", 15, Qt.AlignmentFlag.AlignRight),
    Column("Biến động", 11, Qt.AlignmentFlag.AlignRight),
    Column("Số lệnh", 10, Qt.AlignmentFlag.AlignRight),
)

#: Cell positions within `_KLINE_COLUMNS`, for the ones addressed by name.
(
    _TIME_CELL,
    _OPEN_CELL,
    _HIGH_CELL,
    _LOW_CELL,
    _CLOSE_CELL,
    _VOLUME_CELL,
    _CHANGE_CELL,
    _TRADES_CELL,
) = range(len(_KLINE_COLUMNS))

_KLINE_PAGE_SIZES = [50, 100, 200, 500]


class _KLineRowWidget(DataRow):
    """One row of the KLine table, on the engine's `DataRow`.

    Same `setIndexWidget` pattern as `_StatusRowWidget`, for the same
    reason: `KLineInspectorTableModel` addresses its fields by role
    (`data(index, role)`) rather than by `index.column()`, even though
    `columnCount()` returns 11 — it was built for a QML delegate reading
    named roles per row, not for a real per-column `QTableView`.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(_KLINE_COLUMNS, parent=parent)
        self.setFixedHeight(28)
        self.layout().setContentsMargins(8, 0, 8, 0)
        self.layout().setSpacing(4)

        # Monospace on every cell — a column of prices only lines up if its
        # digits are the same width. A font is a widget API call, not a
        # styling decision, which is why `DataRow.cell()` is reachable.
        for position in range(len(_KLINE_COLUMNS)):
            font = self.cell(position).font()
            font.setFamily("monospace")
            self.cell(position).setFont(font)

        # Volume and trade count recede: they are context for the four price
        # columns, not the figures a user is reading the row for.
        self.set_cell_role(_VOLUME_CELL, StyleRole.CAPTION)
        self.set_cell_role(_TRADES_CELL, StyleRole.CAPTION)
        self.set_cell_role(_CLOSE_CELL, StyleRole.TABLE_CELL_STRONG)

    def apply_row(self, index: QModelIndex, row_number: int) -> None:
        model = index.model()
        model_roles = _kline_model_class(model)
        is_bullish = bool(model.data(index, model_roles.IsBullishRole))
        tone = Tone.POSITIVE if is_bullish else Tone.NEGATIVE

        # Zebra striping, scoped to this class so it cannot cascade into the
        # cells — the unscoped form is a bare property list, which is Qt's
        # universal selector and overrides a child's own colour (`BUG-008`).
        stripe = Palette.BG_CARD if row_number % 2 == 0 else Palette.BG
        self.setStyleSheet(f"{type(self).__name__} {{ background-color: {stripe}; }}")

        self.set_cells(
            [
                str(model.data(index, model_roles.FormattedTimeRole) or ""),
                str(model.data(index, model_roles.OpenRole) or "0"),
                str(model.data(index, model_roles.HighRole) or "0"),
                str(model.data(index, model_roles.LowRole) or "0"),
                str(model.data(index, model_roles.CloseRole) or "0"),
                str(model.data(index, model_roles.VolumeRole) or "0"),
                str(model.data(index, model_roles.ChangePctRole) or "0.00%"),
                str(model.data(index, model_roles.TradesRole) or 0),
            ]
        )
        self.set_cell_role(_CLOSE_CELL, StyleRole.TABLE_CELL_STRONG)
        self.set_cell_tone(_CLOSE_CELL, tone)
        self.set_cell_role(_CHANGE_CELL, StyleRole.TABLE_CELL)
        self.set_cell_tone(_CHANGE_CELL, tone)


def _kline_model_class(model) -> type[KLineInspectorTableModel]:
    """`index.model()` is the real `KLineInspectorTableModel` here (no proxy,
    unlike the status table) — this just gives the role constants a typed
    name to read at the call site."""
    return type(model)


class KLineInspectorDialog(Overlay):
    """Port of `KLineInspectorModal.qml`: jump-to-date + audit controls,
    an audit result banner, the paginated KLine table (`QListView` +
    `setIndexWidget`, same reasoning as `_StatusRowWidget`), and a bottom
    pagination bar with page-size buttons. Stays alive for the view's
    lifetime (like the QML `Popup` it replaces) and wires directly to
    `DataManagementViewModel` signals rather than being rebuilt per open.

    The header and the modal chrome come from `Overlay`; the subtitle it
    already owns is the one `_sync_header()` rewrites per page. The title
    is re-roled to `HEADING`: this app gives its data inspectors and its
    destructive confirms an accent heading, louder than the label
    `Overlay` applies for the eleven Backtest parameter modals.
    """

    def __init__(
        self, view_model: DataManagementViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("TRA CỨU DỮ LIỆU NẾN (KLINE INSPECTOR)", parent=parent)
        self.setObjectName("klineInspectorModal")
        self._view_model = view_model
        self.resize(840, 600)
        apply_role(self.title_label, StyleRole.HEADING)
        # The subtitle is filled by `_sync_header()`, never at construction,
        # so it starts hidden and must be shown once there is a page to
        # describe.
        self._subtitle_label.setVisible(True)

        outer = self.body_layout
        outer.setSpacing(10)

        outer.addLayout(self._build_controls_row())
        outer.addWidget(self._build_audit_banner())
        outer.addWidget(self._build_column_header())
        outer.addWidget(self._build_table(), 1)
        outer.addWidget(self._build_pagination_bar())

        view_model.klineInspectorChanged.connect(self._sync_header)
        view_model.auditResultChanged.connect(self._sync_audit)
        view_model.klineInspectorModel.modelReset.connect(self._rebuild_rows)

        self._sync_header()
        self._sync_audit()
        self._rebuild_rows()

    def _build_controls_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self._txt_jump_date = QLineEdit()
        self._txt_jump_date.setObjectName("txtJumpDate")
        self._txt_jump_date.setPlaceholderText("YYYY-MM-DD...")
        self._txt_jump_date.setFixedWidth(160)
        self._txt_jump_date.setStyleSheet(field_style())
        self._txt_jump_date.returnPressed.connect(self._on_jump)
        row.addWidget(self._txt_jump_date)

        btn_jump = QPushButton("Nhảy tới ngày")
        btn_jump.setObjectName("btnJump")
        btn_jump.setFixedHeight(32)
        btn_jump.clicked.connect(self._on_jump)
        row.addWidget(btn_jump)

        row.addStretch()

        self._btn_audit = QPushButton("Kiểm định Dữ liệu (Audit)")
        self._btn_audit.setObjectName("btnAudit")
        self._btn_audit.setIcon(
            get_icon_loader().get_icon("shield", Palette.TEXT_PRIMARY, 14)
        )
        self._btn_audit.setFixedHeight(32)
        self._btn_audit.setStyleSheet(
            f"QPushButton {{ background-color: {Palette.SUCCESS}; color: {Palette.TEXT_PRIMARY}; "
            f"font-weight: bold; border-radius: 4px; padding: 0 10px; }} "
            f"QPushButton:disabled {{ background-color: {Palette.STATE_IDLE_BG}; color: {Palette.MUTED}; }}"
        )
        self._btn_audit.clicked.connect(self._on_audit)
        row.addWidget(self._btn_audit)

        return row

    def _build_audit_banner(self) -> Banner:
        # The banner `Severity.SUCCESS` was added for: it recolours itself on
        # every sync depending on whether the check passed, which is the one
        # thing `Banner` is settable-after-construction for.
        self._audit_banner = Banner(severity=Severity.SUCCESS)
        self._audit_banner.setFixedHeight(36)
        # `Banner` is a `Panel` and inherits Qt's default layout margins;
        # this one is fixed at 36px tall and was built at 8px horizontally.
        self._audit_banner.body_layout.setContentsMargins(8, 0, 8, 0)
        return self._audit_banner

    def _build_column_header(self) -> QFrame:
        header = QFrame()
        header.setFixedHeight(28)
        apply_role(header, StyleRole.TABLE_HEADER)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(4)
        for spec in _KLINE_COLUMNS:
            label = QLabel(spec.label)
            label.setAlignment(spec.alignment | Qt.AlignmentFlag.AlignVCenter)
            apply_role(label, StyleRole.SECTION_LABEL)
            layout.addWidget(label, spec.stretch)
        return header

    def _build_table(self) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._kline_list = QListView()
        self._kline_list.setObjectName("klineList")
        self._kline_list.setStyleSheet(
            f"background-color: transparent; border: none; color: {Palette.TEXT_PRIMARY};"
        )
        self._kline_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._kline_list.setUniformItemSizes(True)
        self._kline_list.setItemDelegate(RowWidgetDelegate(self._kline_list))
        self._kline_list.setModel(self._view_model.klineInspectorModel)
        layout.addWidget(self._kline_list, 1)

        self._empty_label = QLabel("Không có dữ liệu nến nào trong cơ sở dữ liệu.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 12px;")
        layout.addWidget(self._empty_label)

        return host

    def _build_pagination_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(36)
        apply_role(bar, StyleRole.TABLE_HEADER)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        self._count_label = QLabel()
        self._count_label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 11px;")
        layout.addWidget(self._count_label)
        layout.addStretch()

        page_size_hint = QLabel("Số nến/trang:")
        page_size_hint.setStyleSheet(f"color: {Palette.MUTED}; font-size: 11px;")
        layout.addWidget(page_size_hint)

        self._page_size_buttons: dict[int, QPushButton] = {}
        for size in _KLINE_PAGE_SIZES:
            button = QPushButton(str(size))
            button.setFixedSize(36, 24)
            button.clicked.connect(
                lambda _checked, s=size: self._view_model.requestKlinePageSize(s)
            )
            layout.addWidget(button)
            self._page_size_buttons[size] = button

        self._btn_first_page = QPushButton("<<")
        self._btn_first_page.setFixedSize(32, 26)
        self._btn_first_page.clicked.connect(
            lambda: self._view_model.requestKlinePage(1)
        )
        layout.addWidget(self._btn_first_page)

        self._btn_prev_page = QPushButton("<")
        self._btn_prev_page.setFixedSize(28, 26)
        self._btn_prev_page.clicked.connect(
            lambda: self._view_model.requestKlinePage(
                self._view_model.klineInspectorCurrentPage - 1
            )
        )
        layout.addWidget(self._btn_prev_page)

        self._page_label = QLabel()
        self._page_label.setStyleSheet(
            f"color: {Palette.TEXT_PRIMARY}; font-size: 11px; font-weight: bold;"
        )
        layout.addWidget(self._page_label)

        self._btn_next_page = QPushButton(">")
        self._btn_next_page.setFixedSize(28, 26)
        self._btn_next_page.clicked.connect(
            lambda: self._view_model.requestKlinePage(
                self._view_model.klineInspectorCurrentPage + 1
            )
        )
        layout.addWidget(self._btn_next_page)

        self._btn_last_page = QPushButton(">>")
        self._btn_last_page.setFixedSize(32, 26)
        self._btn_last_page.clicked.connect(
            lambda: self._view_model.requestKlinePage(
                self._view_model.klineInspectorTotalPages
            )
        )
        layout.addWidget(self._btn_last_page)

        return bar

    def _on_jump(self) -> None:
        text = self._txt_jump_date.text()
        if text:
            self._view_model.requestKlineJumpToDate(text)

    def _on_audit(self) -> None:
        vm = self._view_model
        vm.requestRunAudit(vm.klineInspectorSymbol, vm.klineInspectorInterval)

    def _sync_header(self) -> None:
        vm = self._view_model
        self._subtitle_label.setText(
            f"{vm.klineInspectorSymbol} ({vm.klineInspectorInterval}) • "
            f"{vm.klineInspectorTotalRecords} nến • "
            f"Trang {vm.klineInspectorCurrentPage}/{vm.klineInspectorTotalPages}"
        )
        self._count_label.setText(
            f"Hiển thị {vm.klineInspectorModel.rowCount()} / "
            f"{vm.klineInspectorTotalRecords} nến"
        )
        self._page_label.setText(
            f"Trang {vm.klineInspectorCurrentPage} / {vm.klineInspectorTotalPages}"
        )

        current_page = vm.klineInspectorCurrentPage
        total_pages = vm.klineInspectorTotalPages
        self._btn_first_page.setEnabled(current_page > 1)
        self._btn_prev_page.setEnabled(current_page > 1)
        self._btn_next_page.setEnabled(current_page < total_pages)
        self._btn_last_page.setEnabled(current_page < total_pages)

        page_size = vm.klineInspectorPageSize
        for size, button in self._page_size_buttons.items():
            selected = size == page_size
            button.setStyleSheet(
                f"QPushButton {{ background-color: {Palette.ACCENT if selected else Palette.STATE_IDLE_BG}; "
                f"color: {Palette.BG if selected else Palette.TEXT_PRIMARY}; "
                f"font-size: 10px; font-weight: {'bold' if selected else 'normal'}; "
                f"border-radius: 3px; }} "
                f"QPushButton:hover {{ background-color: {Palette.ACCENT if selected else Palette.STATE_HOVER_BG}; }}"
            )

    def _sync_audit(self) -> None:
        vm = self._view_model
        self._btn_audit.setEnabled(not vm.auditRunning)
        self._btn_audit.setText(
            "Đang kiểm định..." if vm.auditRunning else "Kiểm định Dữ liệu (Audit)"
        )

        has_summary = bool(vm.auditSummaryText)
        self._audit_banner.setVisible(has_summary)
        if has_summary:
            self._audit_banner.icon = "✅" if vm.auditPassed else "⚠️"
            self._audit_banner.set_severity(
                Severity.SUCCESS if vm.auditPassed else Severity.DANGER
            )
            self._audit_banner.message = vm.auditSummaryText

    def _rebuild_rows(self) -> None:
        model = self._view_model.klineInspectorModel
        row_count = model.rowCount()
        for row in range(row_count):
            index = model.index(row, 0)
            widget = _KLineRowWidget()
            widget.apply_row(index, row)
            self._kline_list.setIndexWidget(index, widget)
        self._empty_label.setVisible(row_count == 0)
        self._sync_header()


#: The gap table's five data columns — matches `GapInspectorModal.qml`'s
#: Repeater header (weights 0.6/2.5/2.5/1.2/1.4).
_GAP_COLUMNS = (
    Column("#", 6),
    Column("START (FROM)", 25),
    Column("END (TO)", 25),
    Column("DURATION", 12),
    Column("MISSING", 14),
)

#: The heading's sixth column. Not a `Column` — the row has no cell under
#: it, only the repair button, which spends this as `action_stretch`.
_GAP_ACTION_COLUMN = Column("ACTION", 18)

#: Cell positions within `_GAP_COLUMNS`, for the ones addressed by name.
_GAP_ID_CELL, _GAP_START_CELL, _GAP_END_CELL, _GAP_DURATION_CELL, _GAP_MISSING_CELL = (
    range(len(_GAP_COLUMNS))
)

#: The one row action.
_REPAIR_ACTION = 0


class _GapRowWidget(DataRow):
    """One row of the gap table, on the engine's `DataRow`.

    `gapList` is a plain `QVariantList` (`list[dict]`), not a Qt model, so
    these rows are built from Python data directly rather than through
    `setIndexWidget` — which is why the dialog owning them rebuilds the
    whole list on every refresh.
    """

    def __init__(
        self,
        index: int,
        gap: dict,
        on_repair: Callable[[dict], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            _GAP_COLUMNS,
            actions=[RowAction("Vá Gap")],
            action_stretch=_GAP_ACTION_COLUMN.stretch,
            parent=parent,
        )
        self.setFixedHeight(36)
        self.layout().setContentsMargins(8, 0, 8, 0)
        self.layout().setSpacing(6)

        # Zebra striping, scoped to this class so it cannot cascade into the
        # cells — an unscoped property list is Qt's universal selector and
        # overrides a child's own colour (`BUG-008`).
        if index % 2:
            self.setStyleSheet(
                f"{type(self).__name__} {{ background-color: "
                f"{Palette.BG_CARD_HEADER}; border-radius: 4px; }}"
            )

        self.set_cell_role(_GAP_ID_CELL, StyleRole.CAPTION)
        self.set_cell_role(_GAP_DURATION_CELL, StyleRole.TABLE_CELL_STRONG)
        # Accent marks the duration as the notable field — not a `Tone`,
        # because "notable" is not a judgement about the value.
        self.set_cell_colour(_GAP_DURATION_CELL, "accent")
        self.set_cell_role(_GAP_MISSING_CELL, StyleRole.TABLE_CELL_STRONG)
        self.set_cell_tone(_GAP_MISSING_CELL, Tone.NEGATIVE)

        self.set_cells(
            [
                str(gap.get("gap_id") or (index + 1)),
                str(gap.get("start_time") or ""),
                str(gap.get("end_time") or ""),
                str(gap.get("duration_text") or ""),
                f"-{gap.get('missing_candles') or 0} nến",
            ]
        )

        repair_button = self.action_buttons[_REPAIR_ACTION]
        repair_button.setObjectName(f"btnRepairGap_{index}")
        repair_button.setFixedHeight(24)
        self.action_triggered.connect(lambda _position: on_repair(gap))

    def set_enabled(self, enabled: bool) -> None:
        self.action_buttons[_REPAIR_ACTION].setEnabled(enabled)


class _CoverageSegmentWidget(QFrame):  # base-exempt: a coloured bar segment
    """One segment of the timeline coverage bar — port of the QML `Repeater`
    inside the coverage `Rectangle`. Width is proportional to `ratio` within
    its host's `resizeEvent`-driven layout (a plain `QHBoxLayout` with
    stretch factors does the same job as QML's `width: parent.width * ratio`,
    since Qt layouts already distribute width by relative stretch).

    **Deviates from `EPIC-007F` requirement 5, which said to inherit
    `Panel`.** That instruction predates two things learned during the
    task: `Panel` applies `SURFACE`, so this segment would inherit a card
    background, a border and a radius — every one of which it then has to
    override, because it is a flat translucent block of one domain colour.
    Inheriting a base only to undo all of it is worse than saying plainly
    that this is not a surface. Recorded rather than done silently."""

    def __init__(self, segment: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        is_gap = bool(segment.get("is_gap"))
        color = Palette.DANGER if is_gap else Palette.SUCCESS
        opacity = "e6" if is_gap else "bf"  # ~0.9 / ~0.75 alpha, matches QML
        self.setStyleSheet(f"background-color: {color}{opacity};")
        tip = (
            f"{'⚠️ GAP: ' if is_gap else '✅ DATA: '}"
            f"{segment.get('start_time', '')} → {segment.get('end_time', '')} "
            f"({segment.get('candle_count', 0)} nến)"
        )
        self.setToolTip(tip)


class GapInspectorDialog(Overlay):
    """Port of `GapInspectorModal.qml`: timeline coverage bar, a gaps table
    (plain Python list rows, no Qt model — `gapList`/`coverageSegments` are
    `QVariantList` properties, rebuilt wholesale on change same as the QML
    `Repeater` did), and footer Repair-All/Close actions. Stays alive for the
    view's lifetime, same as `KLineInspectorDialog`.

    Its Repair-All/Close row is `Overlay`'s footer, supplied through
    `_build_buttons()`. That runs from `Overlay.__init__`, before this
    class's own body — which is fine here because nothing it builds reads
    `_view_model` until a button is actually pressed.
    """

    def __init__(
        self, view_model: DataManagementViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("CHI TIẾT LỖ HỔNG DỮ LIỆU (GAP INSPECTOR)", parent=parent)
        self.setObjectName("gapInspectorModal")
        self._view_model = view_model
        self.resize(680, 520)
        apply_role(self.title_label, StyleRole.HEADING)
        self._subtitle_label.setVisible(True)

        outer = self.body_layout
        outer.setSpacing(12)

        outer.addLayout(self._build_coverage_bar())
        outer.addWidget(self._build_column_header())
        outer.addWidget(self._build_table(), 1)

        view_model.gapInspectorChanged.connect(self._sync_header)
        view_model.gapListChanged.connect(self._rebuild_rows)
        view_model.coverageSegmentsChanged.connect(self._rebuild_coverage_bar)
        view_model.uiModeChanged.connect(self._sync_enabled_state)

        self._sync_header()
        self._rebuild_rows()
        self._rebuild_coverage_bar()

    def _build_coverage_bar(self) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(4)

        header = QHBoxLayout()
        label = QLabel("TIMELINE COVERAGE")
        label.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 10px; font-weight: bold; letter-spacing: 1px;"
        )
        header.addWidget(label)
        header.addStretch()
        self._coverage_pct_label = QLabel()
        header.addWidget(self._coverage_pct_label)
        box.addLayout(header)

        self._coverage_bar_frame = QFrame()
        self._coverage_bar_frame.setFixedHeight(18)
        # Scoped by hand rather than given `SURFACE`: this is an 18px-tall
        # meter whose children are the coloured coverage segments, and
        # `SURFACE`'s 8px radius would round a bar half that height.
        self._coverage_bar_frame.setStyleSheet(
            f"QFrame {{ background-color: {Palette.BG_CARD}; "
            f"border: 1px solid {Palette.BORDER}; border-radius: 4px; }}"
        )
        self._coverage_bar_layout = QHBoxLayout(self._coverage_bar_frame)
        self._coverage_bar_layout.setContentsMargins(1, 1, 1, 1)
        self._coverage_bar_layout.setSpacing(0)
        box.addWidget(self._coverage_bar_frame)

        return box

    def _build_column_header(self) -> QFrame:
        header = QFrame()
        header.setFixedHeight(28)
        apply_role(header, StyleRole.TABLE_HEADER)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)
        for spec in (*_GAP_COLUMNS, _GAP_ACTION_COLUMN):
            label = QLabel(spec.label)
            apply_role(label, StyleRole.SECTION_LABEL)
            layout.addWidget(label, spec.stretch)
        return header

    def _build_table(self) -> QWidget:
        host = QWidget()
        host.setObjectName("gapListView")
        self._rows_layout = QVBoxLayout(host)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(2)

        self._empty_label = QLabel(
            "Không có lỗ hổng nào được phát hiện (Dữ liệu liên tục 100%)."
        )
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            f"color: {Palette.SUCCESS}; font-size: 12px; font-weight: bold;"
        )
        self._rows_layout.addWidget(self._empty_label)
        self._rows_layout.addStretch(1)

        # The rows host paints the card colour itself. It used to inherit it
        # from the dialog's own unscoped stylesheet — which is to say from
        # `BUG-008` — and lost it the moment the dialog moved onto `Overlay`
        # and got a properly scoped one, leaving a white panel behind the
        # rows. Scoped by `objectName` so it reaches this widget only.
        host.setStyleSheet(f"#gapListView {{ background-color: {Palette.BG_CARD}; }}")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # Scoped: unscoped, `border: none` would strip the border from every
        # descendant that does not set one of its own (`BUG-008`), and this
        # scroll area contains the whole gap-row list. The viewport is a
        # child widget of its own, so it needs naming separately — the
        # scroll area's own rule does not reach it.
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; }}"
            f"QScrollArea > QWidget > QWidget {{ background-color: {Palette.BG_CARD}; }}"
        )
        scroll.setWidget(host)
        self._row_widgets: list[_GapRowWidget] = []
        return scroll

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        self._total_missing_label = QLabel()
        self._total_missing_label.setStyleSheet(
            f"color: {Palette.DANGER}; font-size: 11px; font-weight: bold;"
        )
        row.addWidget(self._total_missing_label)
        row.addStretch()

        self._btn_repair_all = QPushButton("Vá Toàn Bộ Lỗ Hổng (Repair All)")
        self._btn_repair_all.setObjectName("btnRepairAllGaps")
        self._btn_repair_all.setIcon(
            get_icon_loader().get_icon("zap", Palette.ACCENT, 14)
        )
        self._btn_repair_all.setFixedHeight(32)
        self._btn_repair_all.setStyleSheet(
            f"QPushButton {{ background-color: {Palette.BG_CARD_HEADER}; color: {Palette.ACCENT}; "
            f"border: 1px solid {Palette.ACCENT}; border-radius: 6px; font-size: 11px; "
            f"font-weight: bold; padding: 0 10px; }} "
            f"QPushButton:hover {{ background-color: {Palette.STATE_HOVER_BG}; }} "
            f"QPushButton:disabled {{ color: {Palette.MUTED}; border-color: {Palette.BORDER}; }}"
        )
        self._btn_repair_all.clicked.connect(self._on_repair_all)
        row.addWidget(self._btn_repair_all)

        btn_close = QPushButton("Đóng")
        btn_close.setFixedSize(80, 32)
        btn_close.setStyleSheet(
            f"QPushButton {{ background-color: {Palette.BG_CARD}; color: {Palette.TEXT_PRIMARY}; "
            f"border: 1px solid {Palette.BORDER}; border-radius: 6px; }}"
        )
        btn_close.clicked.connect(self.close)
        row.addWidget(btn_close)

        return row

    def _on_repair(self, gap: dict) -> None:
        vm = self._view_model
        start = gap.get("fetch_start_time") or gap.get("start_time")
        end = gap.get("fetch_end_time") or gap.get("end_time")
        vm.requestRepairGap(vm.gapInspectorSymbol, vm.gapInspectorInterval, start, end)

    def _on_repair_all(self) -> None:
        vm = self._view_model
        vm.requestRepairAllGaps(vm.gapInspectorSymbol, vm.gapInspectorInterval)

    def _sync_header(self) -> None:
        vm = self._view_model
        self._subtitle_label.setText(
            f"{vm.gapInspectorSymbol} ({vm.gapInspectorInterval}) • "
            f"{vm.gapInspectorTotalGaps} gaps detected"
        )
        coverage_pct = vm.gapInspectorCoveragePct
        self._coverage_pct_label.setText(f"Độ phủ: {coverage_pct}%")
        color = (
            Palette.SUCCESS
            if coverage_pct >= _FULL_COVERAGE_THRESHOLD
            else Palette.ACCENT
        )
        self._coverage_pct_label.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: bold;"
        )
        self._total_missing_label.setText(
            f"Tổng số nến bị thiếu: {vm.gapInspectorTotalMissing} nến"
        )
        self._sync_enabled_state()

    def _sync_enabled_state(self) -> None:
        idle = self._view_model.uiMode == "IDLE"
        has_gaps = len(self._view_model.gapList) > 0
        self._btn_repair_all.setEnabled(idle and has_gaps)
        for row_widget in self._row_widgets:
            row_widget.set_enabled(idle)

    def _rebuild_rows(self) -> None:
        for row_widget in self._row_widgets:
            self._rows_layout.removeWidget(row_widget)
            row_widget.deleteLater()
        self._row_widgets = []

        gaps = self._view_model.gapList
        for index, gap in enumerate(gaps):
            row_widget = _GapRowWidget(index, gap, self._on_repair)
            self._rows_layout.insertWidget(index, row_widget)
            self._row_widgets.append(row_widget)

        self._empty_label.setVisible(len(gaps) == 0)
        self._sync_enabled_state()

    def _rebuild_coverage_bar(self) -> None:
        while self._coverage_bar_layout.count():
            item = self._coverage_bar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        segments = self._view_model.coverageSegments
        for segment in segments:
            ratio = segment.get("ratio") or 0.05
            stretch = max(2, round(ratio * 1000))
            self._coverage_bar_layout.addWidget(
                _CoverageSegmentWidget(segment), stretch
            )
