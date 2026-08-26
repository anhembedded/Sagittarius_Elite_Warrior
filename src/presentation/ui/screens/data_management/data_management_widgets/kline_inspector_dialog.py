"""The K-line inspector dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Banner,
    Overlay,
    Severity,
    StyleRole,
    apply_role,
)

from ._kline_columns import _KLINE_COLUMNS
from ._kline_row import _KLineRowWidget
from .field_style import field_style
from .row_delegate import RowWidgetDelegate

if TYPE_CHECKING:
    from ..data_management_view_model import DataManagementViewModel


_KLINE_PAGE_SIZES = [50, 100, 200, 500]


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
