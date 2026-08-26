"""The Data Management screen.

`_tint_color` stays here: the view is its only caller."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
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
from Sagittarius_Elite_Warrior.src.presentation.ui.components.app_log_panel import (
    AppLogPanel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.app_progress_bar import (
    AppProgressBar,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.symbol_picker_overlay import (
    SymbolPickerOverlay,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    ConfirmOverlay,
    StyleRole,
    apply_role,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_widgets import (
    GapInspectorDialog,
    KLineInspectorDialog,
    RowWidgetDelegate,
    TimeRangeCardWidget,
    field_style,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView

from ._status_columns import _ACTIONS_COLUMN, _STATUS_COLUMNS
from ._status_row import _StatusRowWidget

if TYPE_CHECKING:
    from .data_management_view_model import DataManagementViewModel


_ACTION_BUTTONS = [
    (
        "btnCheckStatus",
        "Scan Current Status",
        "database",
        "muted",
        "requestCheckStatus",
    ),
    (
        "btnCheckAll",
        "Scan All Shards & Timeframes",
        "layout-dashboard",
        "muted",
        "requestCheckAllStatus",
    ),
    ("btnSyncData", "Sync Current Timeframe", "play", "success", "requestSync"),
    ("btnSyncAllGaps", "Sync All Gaps", "clock", "success", "requestSyncAllGaps"),
    ("btnClearData", "Clear Selected Local Data", "trash-2", "danger", None),
]

_IDLE_MODE = "IDLE"


def _tint_color(tint: str) -> str:
    return {"success": Palette.SUCCESS, "danger": Palette.DANGER}.get(
        tint, Palette.MUTED
    )


class DataManagementView(BaseView):
    """
    @brief The View for the Database screen ("Storage Vault") — QtWidgets (EPIC-005E).

    @details
    Migrated off `QmlHostView`/`DatabaseScreen.qml` (kept on disk, unloaded) the same
    way `SettingsView` was (EPIC-005D): `DataManagementPresenter`/
    `DataManagementViewModel`/every `Coordinator` are unchanged — this class only
    rebuilds the render layer, wiring the same view-model signals by hand instead of
    through QML property bindings.

    `statusModel`/`logModel`/`klineInspectorModel` are QML `Property(..., constant=True)`
    — set once here and never reassigned; their own Qt model signals
    (`dataChanged`/`rowsInserted`/...) drive the `QListView`s directly, same as they
    drove QML's `ListView`s.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model: DataManagementViewModel | None = None
        self._symbol_picker: SymbolPickerOverlay | None = None
        self._kline_inspector: KLineInspectorDialog | None = None
        self._gap_inspector: GapInspectorDialog | None = None
        self._build_ui()

    def apply_ui_mode(self, mode, section_key: str = "main") -> None:
        """Receives FSM state changes from BasePresenter's `_bind_fsm_to_ui`
        callback and forwards them to the view model's `uiMode` property.

        Ported from `QmlHostView.apply_ui_mode` (this screen used to inherit
        it) rather than dropped: `_bind_fsm_to_ui` duck-types this method via
        `hasattr` and silently no-ops (just a log warning) if it's missing —
        without this override, every FSM transition on the real app would
        stop reaching `viewModel.uiMode` and every `uiMode == "IDLE"` gate
        this screen has (Vacuum/Purge/sync buttons, row actions, TimeRangeCard
        read-only) would freeze at whatever mode was current when the screen
        opened. Caught by an integration test that drives the real FSM
        instead of setting `uiMode` directly, not by manual smoke-testing.
        """
        if self._view_model is None:
            return
        mode_value = getattr(mode, "value", mode)
        self._view_model.set_ui_mode(str(mode_value))

    # ------------------------------------------------------------------ #
    # Wiring
    # ------------------------------------------------------------------ #

    def set_view_model(self, view_model: DataManagementViewModel) -> None:
        self._view_model = view_model

        self._log_panel.set_log_model(view_model.logModel)
        self._status_list.setModel(view_model.statusModel)
        view_model.statusModel.rowsInserted.connect(self._on_rows_changed)
        view_model.statusModel.rowsRemoved.connect(self._on_rows_changed)
        view_model.statusModel.modelReset.connect(self._on_rows_changed)
        view_model.statusModel.dataChanged.connect(self._on_data_changed)

        self._cbo_symbol.addItems(view_model.symbols)
        self._cbo_symbol.setCurrentText(view_model.selectedSymbol)
        self._cbo_interval.addItems(view_model.intervals)
        self._cbo_interval.setCurrentText(view_model.selectedInterval)

        self._cbo_symbol.currentTextChanged.connect(self._on_symbol_text_changed)
        self._cbo_interval.currentTextChanged.connect(self._on_interval_changed)
        self._search_field.textEdited.connect(self._on_search_edited)

        self._time_range.set_use_custom_time(view_model.useCustomTime)
        self._time_range.set_from_date_time(view_model.fromDateTime)
        self._time_range.set_to_date_time(view_model.toDateTime)
        self._time_range.customTimeToggled.connect(self._on_custom_time_toggled)
        self._time_range.fromDateTimeEdited.connect(self._on_from_edited)
        self._time_range.toDateTimeEdited.connect(self._on_to_edited)

        self._btn_vacuum.clicked.connect(view_model.requestVacuum)
        self._btn_purge.clicked.connect(self._purge_dialog.open)

        for object_name, _label, _icon, _tint, method_name in _ACTION_BUTTONS:
            button = self._action_buttons[object_name]
            if method_name is not None:
                button.clicked.connect(getattr(view_model, method_name))
        self._action_buttons["btnClearData"].clicked.connect(self._clear_dialog.open)

        self._btn_cancel_sync.clicked.connect(view_model.requestCancel)
        view_model.openKlineInspectorRequested.connect(self._open_kline_inspector)
        view_model.openGapInspectorRequested.connect(self._open_gap_inspector)

        view_model.selectedSymbolChanged.connect(self._sync_symbol_combo)
        view_model.selectedIntervalChanged.connect(self._sync_interval_combo)
        view_model.symbolOptionsChanged.connect(self._noop)  # picker re-reads live
        view_model.useCustomTimeChanged.connect(
            lambda: self._time_range.set_use_custom_time(view_model.useCustomTime)
        )
        view_model.customRangeChanged.connect(self._sync_time_range)
        view_model.progressChanged.connect(self._sync_progress)
        view_model.statsChanged.connect(self._sync_stats)
        view_model.uiModeChanged.connect(self._sync_ui_mode)

        self._sync_stats()
        self._sync_progress()
        self._sync_ui_mode()

    @staticmethod
    def _noop() -> None:
        pass

    # ------------------------------------------------------------------ #
    # Symbol / interval / search
    # ------------------------------------------------------------------ #

    def _on_symbol_text_changed(self, text: str) -> None:
        if self._view_model is not None and text.strip():
            self._view_model.selectedSymbol = text

    def _on_interval_changed(self, text: str) -> None:
        if self._view_model is not None and text.strip():
            self._view_model.selectedInterval = text

    def _sync_symbol_combo(self) -> None:
        if self._cbo_symbol.currentText() != self._view_model.selectedSymbol:
            self._cbo_symbol.setCurrentText(self._view_model.selectedSymbol)

    def _sync_interval_combo(self) -> None:
        if self._cbo_interval.currentText() != self._view_model.selectedInterval:
            self._cbo_interval.setCurrentText(self._view_model.selectedInterval)

    def _on_search_edited(self, text: str) -> None:
        if self._view_model is not None:
            self._view_model.searchText = text

    def _open_symbol_picker(self) -> None:
        if self._view_model is None:
            return
        if self._symbol_picker is None:
            self._symbol_picker = SymbolPickerOverlay(
                get_options=lambda: self._view_model.symbolOptions,
                on_symbol_chosen=self._choose_symbol,
                parent=self,
            )
        self._symbol_picker.open()

    def _choose_symbol(self, symbol: str) -> None:
        if self._view_model is not None:
            self._view_model.selectedSymbol = symbol

    def _open_kline_inspector(self) -> None:
        if self._view_model is None:
            return
        if self._kline_inspector is None:
            self._kline_inspector = KLineInspectorDialog(self._view_model, parent=self)
        self._kline_inspector.open()

    def _open_gap_inspector(self) -> None:
        if self._view_model is None:
            return
        if self._gap_inspector is None:
            self._gap_inspector = GapInspectorDialog(self._view_model, parent=self)
        self._gap_inspector.open()

    # ------------------------------------------------------------------ #
    # Time range
    # ------------------------------------------------------------------ #

    def _on_custom_time_toggled(self, checked: bool) -> None:
        if self._view_model is not None:
            self._view_model.useCustomTime = checked

    def _on_from_edited(self, text: str) -> None:
        if self._view_model is not None:
            self._view_model.fromDateTime = text

    def _on_to_edited(self, text: str) -> None:
        if self._view_model is not None:
            self._view_model.toDateTime = text

    def _sync_time_range(self) -> None:
        self._time_range.set_from_date_time(self._view_model.fromDateTime)
        self._time_range.set_to_date_time(self._view_model.toDateTime)

    # ------------------------------------------------------------------ #
    # Progress / stats / uiMode
    # ------------------------------------------------------------------ #

    def _sync_progress(self) -> None:
        vm = self._view_model
        self._progress_container.setVisible(vm.progressVisible)
        self._progress_bar.set_status_text(vm.progressText)
        self._progress_bar.set_indeterminate(vm.progressMaximum == 0)
        if vm.progressMaximum > 0:
            self._progress_bar.set_range(0, vm.progressMaximum)
            self._progress_bar.set_value(vm.progressValue)
        is_cancelling = vm.uiMode == "CANCELLING"
        self._btn_cancel_sync.setText(
            "Đang hủy..." if is_cancelling else "Hủy Tiến Trình (Cancel)"
        )
        self._btn_cancel_sync.setEnabled(not is_cancelling)

    def _sync_stats(self) -> None:
        self._stat_records_value.setText(self._view_model.storedRecords)
        self._stat_size_value.setText(self._view_model.databaseSize)

    def _sync_ui_mode(self) -> None:
        vm = self._view_model
        idle = vm.uiMode == _IDLE_MODE
        self._btn_vacuum.setEnabled(idle)
        self._btn_purge.setEnabled(idle)
        self._cbo_symbol.setEnabled(idle)
        self._btn_search_symbol.setEnabled(idle)
        self._cbo_interval.setEnabled(idle)
        self._time_range.set_read_only(not idle)
        for object_name, *_rest in _ACTION_BUTTONS:
            self._action_buttons[object_name].setEnabled(idle)
        self._sync_progress()
        for i in range(
            self._status_list.model().rowCount() if self._status_list.model() else 0
        ):
            widget = self._status_list.indexWidget(
                self._status_list.model().index(i, 0)
            )
            if isinstance(widget, _StatusRowWidget):
                widget.apply_ui_mode(idle)

    # ------------------------------------------------------------------ #
    # Status table row widgets
    # ------------------------------------------------------------------ #

    def _on_rows_changed(self, *_args) -> None:
        model = self._status_list.model()
        if model is None:
            return
        self._row_summary_label.setText(
            f"{model.rowCount()} table"
            if model.rowCount() == 1
            else f"{model.rowCount()} tables"
        )
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            if self._status_list.indexWidget(index) is None:
                widget = _StatusRowWidget(self._view_model)
                widget.apply_row(index)
                widget.apply_ui_mode(self._view_model.uiMode == _IDLE_MODE)
                self._status_list.setIndexWidget(index, widget)
        self._empty_label.setVisible(model.rowCount() == 0)

    def _on_data_changed(
        self, top_left: QModelIndex, bottom_right: QModelIndex, _roles
    ) -> None:
        model = self._status_list.model()
        for row in range(top_left.row(), bottom_right.row() + 1):
            index = model.index(row, 0)
            widget = self._status_list.indexWidget(index)
            if isinstance(widget, _StatusRowWidget):
                widget.apply_row(index)

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(14)
        # Scoped: the screen root holds every widget on it, so an unscoped
        # property list here is `BUG-008` at the largest scale a screen has.
        self.setStyleSheet(
            f"{type(self).__name__} {{ background-color: {Palette.BG}; }}"
        )

        outer.addLayout(self._build_header())
        outer.addLayout(self._build_stat_tiles())

        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self._build_sync_controls(), 0)
        body.addLayout(self._build_status_and_log(), 1)
        outer.addLayout(body, 1)

        self._build_dialogs()

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        icon_label = QLabel()
        icon_label.setPixmap(
            get_icon_loader().get_icon("database", Palette.ACCENT).pixmap(22, 22)
        )
        row.addWidget(icon_label)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel("SAGITTARIUS STORAGE VAULT")
        title.setStyleSheet(
            f"color: {Palette.ACCENT}; font-size: 15px; font-weight: bold;"
        )
        subtitle = QLabel("Historical Market KLines Multi-Timeframe Database Hub")
        subtitle.setStyleSheet(f"color: {Palette.MUTED}; font-size: 11px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        row.addLayout(title_box)
        row.addStretch()

        self._btn_vacuum = QPushButton("Tối ưu hóa Database (Vacuum)")
        self._btn_vacuum.setObjectName("btnVacuum")
        self._btn_vacuum.setIcon(get_icon_loader().get_icon("zap", Palette.ACCENT, 14))
        self._btn_vacuum.setStyleSheet(
            f"QPushButton {{ background-color: {Palette.BG_CARD}; color: {Palette.ACCENT}; "
            f"border: 1px solid {Palette.ACCENT}; border-radius: 6px; min-height: 30px; "
            f"font-size: 11px; font-weight: bold; }} "
            f"QPushButton:hover {{ background-color: {Palette.STATE_HOVER_BG}; }}"
        )
        row.addWidget(self._btn_vacuum)

        self._btn_purge = QPushButton("Xóa toàn bộ Vault (Purge)")
        self._btn_purge.setObjectName("btnPurgeVault")
        self._btn_purge.setIcon(
            get_icon_loader().get_icon("trash-2", Palette.DANGER, 14)
        )
        self._btn_purge.setStyleSheet(
            f"QPushButton {{ background-color: {Palette.BG_CARD}; color: {Palette.DANGER}; "
            f"border: 1px solid {Palette.DANGER}; border-radius: 6px; min-height: 30px; "
            f"font-size: 11px; font-weight: bold; }} "
            f"QPushButton:hover {{ background-color: {Palette.BG_CARD_HEADER}; }}"
        )
        row.addWidget(self._btn_purge)

        return row

    def _build_stat_tiles(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        self._stat_records_value = QLabel("—")
        row.addWidget(
            self._build_stat_tile(
                "Stored KLines Records",
                self._stat_records_value,
                "across scanned symbol/interval pairs",
            )
        )
        self._stat_size_value = QLabel("—")
        row.addWidget(
            self._build_stat_tile(
                "Est. Database Size",
                self._stat_size_value,
                "on-disk SQLite storage files (WAL mode)",
            )
        )
        return row

    def _build_stat_tile(
        self, label_text: str, value_label: QLabel, hint_text: str
    ) -> QFrame:
        tile = QFrame()
        # Minimum, not fixed. At `setFixedHeight(74)` the tile was 5px short
        # of its own content — 12+12 margins, three labels of 15/23/13, two
        # gaps of 2 — so the hint line at the bottom rendered cut in half
        # (`BUG-058`). A floor keeps the tiles matching without capping them
        # below what they hold.
        tile.setMinimumHeight(74)
        apply_role(tile, StyleRole.SURFACE)
        layout = QVBoxLayout(tile)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(2)

        label = QLabel(label_text)
        label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 11px;")
        layout.addWidget(label)

        value_label.setObjectName(f"statValue_{label_text}")
        value_label.setStyleSheet(
            f"color: {Palette.TEXT_PRIMARY}; font-size: 18px; font-weight: bold;"
        )
        layout.addWidget(value_label)

        hint = QLabel(hint_text)
        hint.setStyleSheet(f"color: {Palette.MUTED}; font-size: 9px;")
        layout.addWidget(hint)

        return tile

    def _build_sync_controls(self) -> QFrame:
        card = QFrame()
        card.setFixedWidth(320)
        apply_role(card, StyleRole.SURFACE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QLabel("SYNC CONTROLS")
        header.setStyleSheet(
            f"color: {Palette.ACCENT}; font-size: 12px; font-weight: bold;"
        )
        layout.addWidget(header)

        layout.addWidget(self._section_label("TARGET & TIMEFRAME"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)

        grid.addWidget(self._field_label("Symbol:"), 0, 0)
        symbol_row = QHBoxLayout()
        self._cbo_symbol = QComboBox()
        self._cbo_symbol.setObjectName("cboSymbol")
        self._cbo_symbol.setEditable(True)
        self._cbo_symbol.setStyleSheet(field_style())
        symbol_row.addWidget(self._cbo_symbol, 1)

        self._btn_search_symbol = QPushButton()
        self._btn_search_symbol.setObjectName("btnSearchSymbol")
        self._btn_search_symbol.setFixedSize(32, 32)
        self._btn_search_symbol.setIcon(
            get_icon_loader().get_icon("search", Palette.MUTED, 14)
        )
        self._btn_search_symbol.setToolTip("Tìm kiếm nhanh trong 1.361+ mã Binance")
        self._btn_search_symbol.setStyleSheet(field_style())
        self._btn_search_symbol.clicked.connect(self._open_symbol_picker)
        symbol_row.addWidget(self._btn_search_symbol)
        symbol_row_host = QWidget()
        symbol_row_host.setLayout(symbol_row)
        grid.addWidget(symbol_row_host, 0, 1)

        grid.addWidget(self._field_label("Timeframe:"), 1, 0)
        self._cbo_interval = QComboBox()
        self._cbo_interval.setObjectName("cboInterval")
        self._cbo_interval.setStyleSheet(field_style())
        grid.addWidget(self._cbo_interval, 1, 1)

        layout.addLayout(grid)

        self._time_range = TimeRangeCardWidget()
        layout.addWidget(self._time_range)

        layout.addWidget(self._section_label("ACTIONS"))

        self._action_buttons: dict[str, QPushButton] = {}
        for object_name, label, icon, tint, _method in _ACTION_BUTTONS:
            button = QPushButton(label)
            button.setObjectName(object_name)
            button.setIcon(get_icon_loader().get_icon(icon, _tint_color(tint), 14))
            border_color = _tint_color(tint) if tint != "muted" else Palette.BORDER
            button.setStyleSheet(
                f"QPushButton {{ background-color: {Palette.STATE_IDLE_BG}; "
                f"color: {Palette.TEXT_PRIMARY}; border: 1px solid {border_color}; "
                f"border-radius: 6px; min-height: 32px; font-size: 12px; text-align: left; "
                f"padding-left: 8px; }} "
                f"QPushButton:hover {{ background-color: {Palette.STATE_HOVER_BG}; }}"
            )
            self._action_buttons[object_name] = button
            layout.addWidget(button)

        self._progress_container = QWidget()
        progress_layout = QVBoxLayout(self._progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(8)

        self._progress_bar = AppProgressBar()
        progress_layout.addWidget(self._progress_bar)

        self._btn_cancel_sync = QPushButton("Hủy Tiến Trình (Cancel)")
        self._btn_cancel_sync.setObjectName("btnCancelSync")
        self._btn_cancel_sync.setFixedHeight(32)
        self._btn_cancel_sync.setStyleSheet(
            f"QPushButton {{ background-color: {Palette.BG_CARD_HEADER}; color: {Palette.DANGER}; "
            f"border: 1px solid {Palette.DANGER}; border-radius: 6px; font-weight: bold; }} "
            f"QPushButton:hover {{ background-color: {Palette.BG_CARD_HEADER}; }}"
        )
        progress_layout.addWidget(self._btn_cancel_sync)

        layout.addWidget(self._progress_container)
        self._progress_container.setVisible(False)

        layout.addStretch()
        return card

    def _build_status_and_log(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(14)

        table_card = QFrame()
        apply_role(table_card, StyleRole.SURFACE)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(12, 12, 12, 12)
        table_layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        title = QLabel("DATABASE STATUS")
        title.setStyleSheet(
            f"color: {Palette.ACCENT}; font-size: 12px; font-weight: bold;"
        )
        header_row.addWidget(title)

        self._row_summary_label = QLabel("0 tables")
        self._row_summary_label.setObjectName("lblRowSummary")
        self._row_summary_label.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 11px;"
        )
        header_row.addWidget(self._row_summary_label)
        header_row.addStretch()

        self._search_field = QLineEdit()
        self._search_field.setObjectName("txtSearch")
        self._search_field.setPlaceholderText("Search symbol / timeframe…")
        self._search_field.setFixedWidth(180)
        self._search_field.setStyleSheet(field_style(extra_height=26))
        header_row.addWidget(self._search_field)
        table_layout.addLayout(header_row)

        column_header = QFrame()
        column_header.setFixedHeight(28)
        apply_role(column_header, StyleRole.TABLE_HEADER)
        column_header_layout = QHBoxLayout(column_header)
        column_header_layout.setContentsMargins(8, 0, 8, 0)
        column_header_layout.setSpacing(6)
        # Same tuple the rows are built from, plus the actions column the
        # rows spend as `action_stretch` — so a column cannot be renamed,
        # re-weighted or reordered in one place and not the other.
        for spec in (*_STATUS_COLUMNS, _ACTIONS_COLUMN):
            label = QLabel(spec.label)
            apply_role(label, StyleRole.SECTION_LABEL)
            column_header_layout.addWidget(label, spec.stretch)
        table_layout.addWidget(column_header)

        self._status_list = QListView()
        self._status_list.setObjectName("statusList")
        self._status_list.setStyleSheet(
            f"background-color: transparent; border: none; color: {Palette.TEXT_PRIMARY};"
        )
        self._status_list.setSelectionMode(QListView.SelectionMode.NoSelection)
        self._status_list.setUniformItemSizes(True)
        self._status_list.setItemDelegate(RowWidgetDelegate(self._status_list))
        table_layout.addWidget(self._status_list, 1)

        self._empty_label = QLabel(
            "Storage Vault trống. Hãy chọn Symbol & Timeframe và nhấn 'Sync' để tải dữ liệu."
        )
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 12px;")
        table_layout.addWidget(self._empty_label)

        column.addWidget(table_card, 1)

        self._log_panel = AppLogPanel("SYNC LOG")
        self._log_panel.setObjectName("syncLogPanel")
        self._log_panel.setFixedHeight(190)
        column.addWidget(self._log_panel)

        return column

    def _build_dialogs(self) -> None:
        """Both destructive confirms, on the engine's `ConfirmOverlay`.

        The app's own `ConfirmDialog` took an `on_confirm` callback and
        called `close()`, which left `exec()` returning `Rejected` even
        after the user confirmed — `ConfirmOverlay` calls `accept()`, so
        the answer is readable the standard Qt way. That rewiring is what
        its docstring said the migration owed, and it is done here: the
        callbacks move to `accepted`.

        The slots stay indirect on purpose. `_build_dialogs()` runs from
        `__init__`, long before `set_view_model()`, so binding
        `self._view_model.requestClearData` here would bind `None`.
        """
        self._clear_dialog = ConfirmOverlay(
            "XÁC NHẬN XÓA DỮ LIỆU",
            "Xóa các nến đã lưu trong SQLite shard",
            message="Bạn có chắc chắn muốn xóa toàn bộ nến của symbol/timeframe đã chọn không? "
            "Thao tác này sẽ giải phóng dung lượng đĩa và làm trống bảng klines tương ứng.",
            confirm_text="Xác nhận Xóa",
            cancel_text="Hủy bỏ",
            danger=True,
            parent=self,
        )
        self._clear_dialog.confirm_button.setObjectName("btnConfirmClear")
        self._clear_dialog.accepted.connect(self._on_clear_confirmed)

        self._purge_dialog = ConfirmOverlay(
            "CẢNH BÁO NGUY HIỂM — PURGE VAULT",
            "Xóa toàn bộ database SQLite",
            message="CẢNH BÁO NGUY HIỂM: Bạn đang chuẩn bị xóa TOÀN BỘ dữ liệu của tất cả các "
            "symbol trong Storage Vault! Hành động này sẽ xóa tất cả các file SQLite shard "
            "(.db) và không thể hoàn tác.",
            confirm_text="XÓA TOÀN BỘ (PURGE)",
            cancel_text="Hủy bỏ",
            danger=True,
            parent=self,
        )
        self._purge_dialog.confirm_button.setObjectName("btnConfirmPurge")
        self._purge_dialog.accepted.connect(self._on_purge_confirmed)

    def _on_clear_confirmed(self) -> None:
        if self._view_model is not None:
            self._view_model.requestClearData()

    def _on_purge_confirmed(self) -> None:
        if self._view_model is not None:
            self._view_model.requestPurgeAll()

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 10px; font-weight: bold; letter-spacing: 1px;"
        )
        return label

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"color: {Palette.TEXT_PRIMARY}; font-size: 12px;")
        return label
