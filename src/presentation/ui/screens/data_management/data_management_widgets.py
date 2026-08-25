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
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)

_FULL_COVERAGE_THRESHOLD = 99.0

if TYPE_CHECKING:
    from .data_management_view_model import DataManagementViewModel
    from .kline_inspector_table_model import KLineInspectorTableModel


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


class TimeRangeCardWidget(QWidget):
    """Port of the engine's `TimeRangeCard.qml`: a "use custom time range"
    toggle plus two free-text From/To fields (not QDateTimeEdit — the QML
    version never validated format at the widget level either; the
    presenter's `_parse_datetime`/`SyncCoordinator.parse_datetime` is the
    real validation, unchanged by this migration)."""

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

        self._apply_enabled_state()

    def _on_toggled(self, checked: bool) -> None:
        self._apply_enabled_state()
        self.customTimeToggled.emit(checked)

    def _apply_enabled_state(self) -> None:
        fields_enabled = self._toggle.isChecked() and not self._read_only
        self._from_field.setEnabled(fields_enabled)
        self._to_field.setEnabled(fields_enabled)
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


class ConfirmDialog(QDialog):
    """Port of the Clear/Purge `ModalDialogCard` confirm dialogs: icon-less
    header (title + subtitle), a message body, Cancel + a danger-styled
    confirm button. Parameterized rather than duplicated once per dialog —
    the QML versions were two near-identical copies of the same shape."""

    def __init__(
        self,
        title: str,
        subtitle: str,
        message: str,
        confirm_text: str,
        confirm_object_name: str,
        on_confirm: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.resize(420, 220)
        self.setStyleSheet(
            f"background-color: {Palette.BG_CARD}; color: {Palette.TEXT_PRIMARY};"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color: {Palette.DANGER}; font-size: 13px; font-weight: bold;"
        )
        layout.addWidget(title_label)

        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 11px;")
        layout.addWidget(subtitle_label)

        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet(f"color: {Palette.TEXT_PRIMARY}; font-size: 13px;")
        layout.addWidget(message_label, 1)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        cancel_button = QPushButton("Hủy bỏ")
        cancel_button.clicked.connect(self.close)
        button_row.addWidget(cancel_button)

        confirm_button = QPushButton(confirm_text)
        confirm_button.setObjectName(confirm_object_name)
        confirm_button.setStyleSheet(
            f"QPushButton {{ background-color: {Palette.DANGER}; color: white; "
            f"font-weight: bold; border-radius: 6px; min-height: 34px; }}"
        )

        def _confirm() -> None:
            self.close()
            on_confirm()

        confirm_button.clicked.connect(_confirm)
        button_row.addWidget(confirm_button)

        layout.addLayout(button_row)


#: (label, Layout stretch) for the KLine table columns — matches
#: KLineInspectorModal.qml's fixed column widths (140/80/80/80/80/105/75/70).
_KLINE_COLUMNS = [
    ("Thời gian (UTC)", 20, Qt.AlignmentFlag.AlignLeft),
    ("Mở (Open)", 11, Qt.AlignmentFlag.AlignRight),
    ("Cao (High)", 11, Qt.AlignmentFlag.AlignRight),
    ("Thấp (Low)", 11, Qt.AlignmentFlag.AlignRight),
    ("Đóng (Close)", 11, Qt.AlignmentFlag.AlignRight),
    ("Khối lượng (Vol)", 15, Qt.AlignmentFlag.AlignRight),
    ("Biến động", 11, Qt.AlignmentFlag.AlignRight),
    ("Số lệnh", 10, Qt.AlignmentFlag.AlignRight),
]

_KLINE_PAGE_SIZES = [50, 100, 200, 500]


class _KLineRowWidget(QFrame):
    """One row of the KLine table — a direct port of
    `KLineInspectorModal.qml`'s `ListView` delegate. Same `setIndexWidget`
    pattern as `_StatusRowWidget`: `KLineInspectorTableModel` addresses its
    fields by role (`data(index, role)`), not by `index.column()`, even
    though `columnCount()` returns 11 — it was built for a QML delegate that
    reads named roles per row, not a real per-column `QTableView`."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(4)

        self._labels: list[QLabel] = []
        for _text, stretch, alignment in _KLINE_COLUMNS:
            label = QLabel()
            label.setAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
            label.setStyleSheet(
                f"color: {Palette.TEXT_PRIMARY}; font-size: 11px; font-family: monospace;"
            )
            layout.addWidget(label, stretch)
            self._labels.append(label)

        (
            self._time_label,
            self._open_label,
            self._high_label,
            self._low_label,
            self._close_label,
            self._volume_label,
            self._change_label,
            self._trades_label,
        ) = self._labels

        self._volume_label.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 11px; font-family: monospace;"
        )
        self._trades_label.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 11px; font-family: monospace;"
        )

    def apply_row(self, index: QModelIndex, row_number: int) -> None:
        model = index.model()
        model_roles = _kline_model_class(model)
        is_bullish = bool(model.data(index, model_roles.IsBullishRole))
        color = Palette.SUCCESS if is_bullish else Palette.DANGER

        self.setStyleSheet(
            f"background-color: {Palette.BG_CARD if row_number % 2 == 0 else Palette.BG};"
        )
        self._time_label.setText(
            str(model.data(index, model_roles.FormattedTimeRole) or "")
        )
        self._open_label.setText(str(model.data(index, model_roles.OpenRole) or "0"))
        self._high_label.setText(str(model.data(index, model_roles.HighRole) or "0"))
        self._low_label.setText(str(model.data(index, model_roles.LowRole) or "0"))
        self._close_label.setText(str(model.data(index, model_roles.CloseRole) or "0"))
        self._close_label.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: bold; font-family: monospace;"
        )
        self._volume_label.setText(
            str(model.data(index, model_roles.VolumeRole) or "0")
        )
        self._change_label.setText(
            str(model.data(index, model_roles.ChangePctRole) or "0.00%")
        )
        self._change_label.setStyleSheet(
            f"color: {color}; font-size: 11px; font-family: monospace;"
        )
        self._trades_label.setText(str(model.data(index, model_roles.TradesRole) or 0))


def _kline_model_class(model) -> type[KLineInspectorTableModel]:
    """`index.model()` is the real `KLineInspectorTableModel` here (no proxy,
    unlike the status table) — this just gives the role constants a typed
    name to read at the call site."""
    return type(model)


class KLineInspectorDialog(QDialog):
    """Port of `KLineInspectorModal.qml`: jump-to-date + audit controls,
    an audit result banner, the paginated KLine table (`QListView` +
    `setIndexWidget`, same reasoning as `_StatusRowWidget`), and a bottom
    pagination bar with page-size buttons. Stays alive for the view's
    lifetime (like the QML `Popup` it replaces) and wires directly to
    `DataManagementViewModel` signals rather than being rebuilt per open."""

    def __init__(
        self, view_model: DataManagementViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("klineInspectorModal")
        self._view_model = view_model
        self.setModal(True)
        self.resize(840, 600)
        self.setStyleSheet(
            f"background-color: {Palette.BG_CARD}; color: {Palette.TEXT_PRIMARY};"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        outer.addLayout(self._build_title_row())
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

    def _build_title_row(self) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(2)
        title = QLabel("TRA CỨU DỮ LIỆU NẾN (KLINE INSPECTOR)")
        title.setStyleSheet(
            f"color: {Palette.ACCENT}; font-size: 13px; font-weight: bold;"
        )
        box.addWidget(title)
        self._subtitle_label = QLabel()
        self._subtitle_label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 11px;")
        box.addWidget(self._subtitle_label)
        return box

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

    def _build_audit_banner(self) -> QFrame:
        self._audit_banner = QFrame()
        self._audit_banner.setFixedHeight(36)
        layout = QHBoxLayout(self._audit_banner)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)

        self._audit_icon_label = QLabel()
        layout.addWidget(self._audit_icon_label)

        self._audit_summary_label = QLabel()
        self._audit_summary_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        layout.addWidget(self._audit_summary_label, 1)

        return self._audit_banner

    def _build_column_header(self) -> QFrame:
        header = QFrame()
        header.setFixedHeight(28)
        header.setStyleSheet(
            f"background-color: {Palette.BG_CARD_HEADER}; border-radius: 4px;"
        )
        layout = QHBoxLayout(header)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(4)
        for text, stretch, alignment in _KLINE_COLUMNS:
            label = QLabel(text)
            label.setAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
            label.setStyleSheet(
                f"color: {Palette.MUTED}; font-size: 11px; font-weight: bold;"
            )
            layout.addWidget(label, stretch)
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
        bar.setStyleSheet(
            f"background-color: {Palette.BG_CARD_HEADER}; border-radius: 4px;"
        )
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
            self._audit_icon_label.setText("✅" if vm.auditPassed else "⚠️")
            color = Palette.SUCCESS if vm.auditPassed else Palette.DANGER
            # Uniform ground; pass-vs-fail is carried by `color` below.
            bg = Palette.BG_CARD_HEADER
            self._audit_banner.setStyleSheet(
                f"background-color: {bg}; border: 1px solid {color}; border-radius: 4px;"
            )
            self._audit_summary_label.setStyleSheet(
                f"color: {color}; font-size: 12px; font-weight: bold;"
            )
            self._audit_summary_label.setText(vm.auditSummaryText)

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


#: (label, stretch) for the gap table columns — matches GapInspectorModal.qml's
#: Repeater header (weights 0.6/2.5/2.5/1.2/1.4/1.8).
_GAP_COLUMNS = [
    ("#", 6),
    ("START (FROM)", 25),
    ("END (TO)", 25),
    ("DURATION", 12),
    ("MISSING", 14),
    ("ACTION", 18),
]


class _GapRowWidget(QFrame):
    """One row of the gap table — direct port of GapInspectorModal.qml's
    ListView delegate. `gapList` is a plain `QVariantList` (list[dict]), not
    a Qt model, so rows are rebuilt from Python data directly rather than via
    `setIndexWidget`."""

    def __init__(
        self,
        index: int,
        gap: dict,
        on_repair: Callable[[dict], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setStyleSheet(
            "background-color: transparent;"
            if index % 2 == 0
            else f"background-color: {Palette.BG_CARD_HEADER}; border-radius: 4px;"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        gap_id_label = QLabel(str(gap.get("gap_id") or (index + 1)))
        gap_id_label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 11px;")
        layout.addWidget(gap_id_label, 6)

        start_label = QLabel(str(gap.get("start_time") or ""))
        start_label.setStyleSheet(f"color: {Palette.TEXT_PRIMARY}; font-size: 11px;")
        layout.addWidget(start_label, 25)

        end_label = QLabel(str(gap.get("end_time") or ""))
        end_label.setStyleSheet(f"color: {Palette.TEXT_PRIMARY}; font-size: 11px;")
        layout.addWidget(end_label, 25)

        duration_label = QLabel(str(gap.get("duration_text") or ""))
        duration_label.setStyleSheet(
            f"color: {Palette.ACCENT}; font-size: 11px; font-weight: bold;"
        )
        layout.addWidget(duration_label, 12)

        missing_label = QLabel(f"-{gap.get('missing_candles') or 0} nến")
        missing_label.setStyleSheet(
            f"color: {Palette.DANGER}; font-size: 11px; font-weight: bold;"
        )
        layout.addWidget(missing_label, 14)

        self._repair_button = QPushButton("Vá Gap")
        self._repair_button.setObjectName(f"btnRepairGap_{index}")
        self._repair_button.setFixedHeight(24)
        self._repair_button.setStyleSheet(
            f"QPushButton {{ background-color: {Palette.BG_CARD_HEADER}; color: {Palette.ACCENT}; "
            f"border: 1px solid {Palette.ACCENT}; border-radius: 4px; font-size: 10px; "
            f"font-weight: bold; }} "
            f"QPushButton:hover {{ background-color: {Palette.STATE_HOVER_BG}; }}"
        )
        self._repair_button.clicked.connect(lambda: on_repair(gap))
        layout.addWidget(self._repair_button, 18)

    def set_enabled(self, enabled: bool) -> None:
        self._repair_button.setEnabled(enabled)


class _CoverageSegmentWidget(QFrame):
    """One segment of the timeline coverage bar — port of the QML `Repeater`
    inside the coverage `Rectangle`. Width is proportional to `ratio` within
    its host's `resizeEvent`-driven layout (a plain `QHBoxLayout` with
    stretch factors does the same job as QML's `width: parent.width * ratio`,
    since Qt layouts already distribute width by relative stretch)."""

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


class GapInspectorDialog(QDialog):
    """Port of `GapInspectorModal.qml`: timeline coverage bar, a gaps table
    (plain Python list rows, no Qt model — `gapList`/`coverageSegments` are
    `QVariantList` properties, rebuilt wholesale on change same as the QML
    `Repeater` did), and footer Repair-All/Close actions. Stays alive for the
    view's lifetime, same as `KLineInspectorDialog`."""

    def __init__(
        self, view_model: DataManagementViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("gapInspectorModal")
        self._view_model = view_model
        self.setModal(True)
        self.resize(680, 520)
        self.setStyleSheet(
            f"background-color: {Palette.BG_CARD}; color: {Palette.TEXT_PRIMARY};"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        outer.addLayout(self._build_title_row())
        outer.addLayout(self._build_coverage_bar())
        outer.addWidget(self._build_column_header())
        outer.addWidget(self._build_table(), 1)
        outer.addLayout(self._build_footer())

        view_model.gapInspectorChanged.connect(self._sync_header)
        view_model.gapListChanged.connect(self._rebuild_rows)
        view_model.coverageSegmentsChanged.connect(self._rebuild_coverage_bar)
        view_model.uiModeChanged.connect(self._sync_enabled_state)

        self._sync_header()
        self._rebuild_rows()
        self._rebuild_coverage_bar()

    def _build_title_row(self) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(2)
        title = QLabel("CHI TIẾT LỖ HỔNG DỮ LIỆU (GAP INSPECTOR)")
        title.setStyleSheet(
            f"color: {Palette.ACCENT}; font-size: 13px; font-weight: bold;"
        )
        box.addWidget(title)
        self._subtitle_label = QLabel()
        self._subtitle_label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 11px;")
        box.addWidget(self._subtitle_label)
        return box

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
        self._coverage_bar_frame.setStyleSheet(
            f"background-color: {Palette.BG_CARD}; border: 1px solid {Palette.BORDER}; border-radius: 4px;"
        )
        self._coverage_bar_layout = QHBoxLayout(self._coverage_bar_frame)
        self._coverage_bar_layout.setContentsMargins(1, 1, 1, 1)
        self._coverage_bar_layout.setSpacing(0)
        box.addWidget(self._coverage_bar_frame)

        return box

    def _build_column_header(self) -> QFrame:
        header = QFrame()
        header.setFixedHeight(28)
        header.setStyleSheet(
            f"background-color: {Palette.BG_CARD_HEADER}; border-radius: 4px;"
        )
        layout = QHBoxLayout(header)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)
        for text, stretch in _GAP_COLUMNS:
            label = QLabel(text)
            label.setStyleSheet(
                f"color: {Palette.MUTED}; font-size: 10px; font-weight: bold;"
            )
            layout.addWidget(label, stretch)
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

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # Scoped: unscoped, `border: none` would strip the border from every
        # descendant that does not set one of its own (`BUG-008`), and this
        # scroll area contains the whole gap-row list.
        scroll.setStyleSheet("QScrollArea { border: none; }")
        scroll.setWidget(host)
        self._row_widgets: list[_GapRowWidget] = []
        return scroll

    def _build_footer(self) -> QHBoxLayout:
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
