"""The Data Management screen.

`_tint_color` stays here: the view is its only caller."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
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
from Sagittarius_Elite_Warrior.src.presentation.ui.components.symbol_picker import (
    SymbolPickerOverlay,
    SymbolPreferences,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.timeframe_picker import (
    describe as describe_timeframe,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    ConfirmOverlay,
    PageShell,
    StyleRole,
    apply_role,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.kit.progress_banner_widget import (
    ProgressBannerWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TimeframePicker.timeframe_picker_dialog import (
    PinnedTimeframes,
    TimeframePickerDialog,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_widgets import (
    DatabaseStatusPanel,
    GapInspectorDialog,
    KlineInspectorDialogWidget,
    TimeRangeCardWidget,
    field_style,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView

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
_CANCELLING_MODE = "CANCELLING"

#: `ProgressBanner.qml`'s own default (`"Hủy"`) is shorter than what this
#: screen's `AppProgressBar`-era `QPushButton` said — kept as the explicit
#: label here so the on-screen wording does not silently change as part of
#: this retrofit.
_CANCEL_LABEL = "Hủy Tiến Trình (Cancel)"

#: `ProgressBanner.qml`'s `ColumnLayout` measures to a stable 30px
#: `implicitHeight` at this card's real inner width (292px = the 320px
#: `_build_sync_controls` card minus its 14px side margins), unchanged
#: across every state this screen drives it through (status text set,
#: `indeterminate`, `cancelling`) — verified empirically rather than
#: guessed, since `QQuickWidget.sizeHint()` only echoes whatever size it
#: was last resized to (not the root item's actual `implicitHeight`) and so
#: cannot be trusted to auto-size this widget inside `QVBoxLayout`.
_PROGRESS_BANNER_HEIGHT = 32

#: `describe()` returns `None` for a code the domain no longer recognises
#: (a remembered value on disk that has gone stale, same reasoning as
#: `catalogue.describe`'s own docstring) — this is what the picker's "≈ N
#: nến" summary falls back to when that happens, not a real timeframe.
_FALLBACK_TIMEFRAME_SECONDS = 60


def _timeframe_seconds_for(code: str) -> int:
    option = describe_timeframe(code)
    return option.seconds if option is not None else _FALLBACK_TIMEFRAME_SECONDS


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

    `logModel`/`klineInspectorModel` are QML `Property(..., constant=True)`
    — set once here and never reassigned; their own Qt model signals
    (`dataChanged`/`rowsInserted`/...) drive the `QListView`s directly, same as they
    drove QML's `ListView`s. The status table itself is `DatabaseStatusPanel`
    (EPIC-015 Phase 2) — an embedded QML component, not a `QListView`, built
    lazily in `set_view_model()` the same way `_kline_inspector`/
    `_gap_inspector`/`_timeframe_picker` are, since `_build_ui()` runs before
    a real view model exists to construct it from.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model: DataManagementViewModel | None = None
        self._symbol_picker: SymbolPickerOverlay | None = None
        self._timeframe_picker: TimeframePickerDialog | None = None
        # EPIC-015 bậc 1: private, non-persisted — this picker is its own
        # only consumer — see `timeframe_picker_dialog.py`'s
        # `PinnedTimeframes` docstring.
        self._timeframe_picker_pinned = PinnedTimeframes()
        # EPIC-014: replaced by the container-registered store when the
        # Presenter injects it, so a pair starred here is starred on Backtest
        # and Dev Board too. Self-constructed so a bare view still works.
        self._symbol_preferences = SymbolPreferences()
        self._kline_inspector: KlineInspectorDialogWidget | None = None
        self._gap_inspector: GapInspectorDialog | None = None
        self._status_panel: DatabaseStatusPanel | None = None
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
        if self._status_panel is None:
            self._status_panel = DatabaseStatusPanel(view_model.status_model)
            self._status_panel.rowActionRequested.connect(self._on_status_row_action)
            self._status_column.insertWidget(0, self._status_panel, 1)

        self._btn_symbol.setText(view_model.selectedSymbol)
        self._btn_interval.setText(view_model.selectedInterval)

        self._time_range.set_use_custom_time(view_model.useCustomTime)
        self._time_range.set_from_date_time(view_model.fromDateTime)
        self._time_range.set_to_date_time(view_model.toDateTime)
        self._time_range.set_timeframe_source(
            lambda: _timeframe_seconds_for(view_model.selectedInterval),
            lambda: view_model.selectedInterval,
        )
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

        self._progress_banner.cancelRequested.connect(view_model.requestCancel)
        view_model.openKlineInspectorRequested.connect(self._open_kline_inspector)
        view_model.openGapInspectorRequested.connect(self._open_gap_inspector)

        view_model.selectedSymbolChanged.connect(self._sync_symbol_field)
        view_model.selectedIntervalChanged.connect(self._sync_interval_field)
        view_model.symbolOptionsChanged.connect(self._refresh_symbol_picker)
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

    # ------------------------------------------------------------------ #
    # Symbol / interval
    # ------------------------------------------------------------------ #

    def _on_interval_changed(self, text: str) -> None:
        if self._view_model is not None and text.strip():
            self._view_model.selectedInterval = text

    def _sync_symbol_field(self) -> None:
        if self._btn_symbol.text() != self._view_model.selectedSymbol:
            self._btn_symbol.setText(self._view_model.selectedSymbol)

    def _sync_interval_field(self) -> None:
        if self._btn_interval.text() != self._view_model.selectedInterval:
            self._btn_interval.setText(self._view_model.selectedInterval)

    def set_symbol_preferences(self, preferences: SymbolPreferences) -> None:
        """Swaps in the shared, persisted favourites/recents store — injected
        by `DataManagementPresenter`, which has the container this view does
        not. Rebinds an already-built picker so call order cannot matter."""
        if preferences is self._symbol_preferences:
            return
        if self._symbol_picker is not None:
            self._symbol_preferences.unbind_picker(
                self._symbol_picker, self._choose_symbol
            )
            preferences.bind_picker(self._symbol_picker, self._choose_symbol)
        self._symbol_preferences = preferences

    def _open_symbol_picker(self) -> None:
        if self._view_model is None:
            return
        if self._symbol_picker is None:
            self._symbol_picker = SymbolPickerOverlay(
                get_symbols=lambda: self._view_model.symbolOptions,
                get_favourites=lambda: self._symbol_preferences.favourites,
                get_recents=lambda: self._symbol_preferences.recents,
                get_current=lambda: self._view_model.selectedSymbol,
                parent=self,
            )
            self._symbol_preferences.bind_picker(
                self._symbol_picker, self._choose_symbol
            )
        self._symbol_picker.show()
        self._symbol_picker.raise_()

    def _refresh_symbol_picker(self) -> None:
        """The scan populates `symbolOptions` while the dialog may already be
        open; without this it stays on "Đang tải" until reopened."""
        if self._symbol_picker is not None and self._symbol_picker.isVisible():
            self._symbol_picker.refresh()

    def _choose_symbol(self, symbol: str) -> None:
        if self._view_model is not None:
            self._view_model.selectedSymbol = symbol

    def _open_timeframe_picker(self) -> None:
        if self._view_model is None:
            return
        if self._timeframe_picker is None:
            self._timeframe_picker = TimeframePickerDialog.from_callbacks(
                get_codes=lambda: self._view_model.intervals,
                get_current=lambda: self._view_model.selectedInterval,
                get_pinned=self._timeframe_picker_pinned.get,
                set_pinned=self._timeframe_picker_pinned.set,
                parent=self,
            )
            self._timeframe_picker.chosen.connect(self._on_interval_changed)
        self._timeframe_picker.open_dialog()

    def _open_kline_inspector(self) -> None:
        if self._view_model is None:
            return
        if self._kline_inspector is None:
            self._kline_inspector = KlineInspectorDialogWidget(
                self._view_model, parent=self
            )
        self._kline_inspector.open_dialog()

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
        self._progress_banner.set_status_text(vm.progressText)
        self._progress_banner.set_indeterminate(vm.progressMaximum == 0)
        # `progressPercent` already computes and clamps value/maximum with a
        # `progressMaximum <= 0` guard (`DataManagementViewModel`) — reused
        # rather than re-deriving the same number a second place here.
        self._progress_banner.set_percent(vm.progressPercent)
        # `ProgressBanner.qml`'s own Cancel button relabels/disables itself
        # from `cancelling` — no separate button text/enabled state to set.
        self._progress_banner.set_cancelling(vm.uiMode == _CANCELLING_MODE)

    def _sync_stats(self) -> None:
        self._stat_records_value.setText(self._view_model.storedRecords)
        self._stat_size_value.setText(self._view_model.databaseSize)

    def _sync_ui_mode(self) -> None:
        vm = self._view_model
        idle = vm.uiMode == _IDLE_MODE
        self._btn_vacuum.setEnabled(idle)
        self._btn_purge.setEnabled(idle)
        self._btn_symbol.setEnabled(idle)
        self._btn_interval.setEnabled(idle)
        self._time_range.set_read_only(not idle)
        for object_name, *_rest in _ACTION_BUTTONS:
            self._action_buttons[object_name].setEnabled(idle)
        self._sync_progress()
        if self._status_panel is not None:
            self._status_panel.set_actions_enabled(idle)

    # ------------------------------------------------------------------ #
    # Status table row actions
    # ------------------------------------------------------------------ #

    def _on_status_row_action(self, action: str, symbol: str, interval: str) -> None:
        """`DatabaseStatusPanel.rowActionRequested` — the same four calls
        the old `_status_row.py`'s `_on_action` used to make before it was
        deleted (EPIC-015 Phase 2)."""
        if self._view_model is None:
            return
        request = {
            "klines": self._view_model.requestInspectKlines,
            "gaps": self._view_model.requestInspectGaps,
            "sync": self._view_model.requestSyncRow,
            "clear": self._view_model.requestClearRow,
        }.get(action)
        if request is not None:
            request(symbol, interval)

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        # Scoped: the screen root holds every widget on it, so an unscoped
        # property list here is `BUG-008` at the largest scale a screen has.
        self.setStyleSheet(
            f"{type(self).__name__} {{ background-color: {Palette.BG}; }}"
        )

        shell = PageShell()
        outer.addWidget(shell)
        shell.set_header(
            "SAGITTARIUS STORAGE VAULT",
            "Historical Market KLines Multi-Timeframe Database Hub",
            icon=get_icon_loader().get_icon("database", Palette.ACCENT),
            actions=self._build_header_actions(),
        )

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(14)
        main_layout.addLayout(self._build_stat_tiles())
        main_layout.addLayout(self._build_status_column(), 1)

        # `PageShell.set_workspace`'s rail is always the right-hand pane —
        # this used to be the LEFT column of a plain `QHBoxLayout`, the one
        # placement the Pattern Library rules out ("rail is always on the
        # right, never the left").
        shell.set_workspace(main, rail=self._build_sync_controls())
        shell.set_console(self._build_log_panel())

        self._build_dialogs()

    def _build_header_actions(self) -> list[QPushButton]:
        self._btn_vacuum = QPushButton("Tối ưu hóa Database (Vacuum)")
        self._btn_vacuum.setObjectName("btnVacuum")
        self._btn_vacuum.setIcon(get_icon_loader().get_icon("zap", Palette.ACCENT, 14))
        self._btn_vacuum.setStyleSheet(
            f"QPushButton {{ background-color: {Palette.BG_CARD}; color: {Palette.ACCENT}; "
            f"border: 1px solid {Palette.ACCENT}; border-radius: 6px; min-height: 30px; "
            f"font-size: 11px; font-weight: bold; }} "
            f"QPushButton:hover {{ background-color: {Palette.STATE_HOVER_BG}; }}"
        )

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

        return [self._btn_vacuum, self._btn_purge]

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

        # EPIC-014 — both fields are buttons that open the shared pickers.
        #
        # Symbol was an editable `QComboBox` beside a magnifier button, i.e.
        # two widgets for one choice: the combo let a symbol be typed with
        # nothing to validate it, and the button next to it opened the picker
        # that could have validated it. The button *is* the field now, so
        # there is one way in and it cannot produce an unlisted symbol.
        #
        # Timeframe was a closed combo, which was at least correct — it
        # already offered all sixteen. It becomes a button for the same
        # reason Backtest's did: one shape for "choose a timeframe" across
        # every screen, with the unit spelled out on each card.
        grid.addWidget(self._field_label("Symbol:"), 0, 0)
        self._btn_symbol = QPushButton()
        self._btn_symbol.setObjectName("btnSymbol")
        self._btn_symbol.setFixedHeight(32)
        self._btn_symbol.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_symbol.setIcon(
            get_icon_loader().get_icon("search", Palette.MUTED, 14)
        )
        self._btn_symbol.setToolTip("Tìm kiếm nhanh trong 1.361+ mã Binance")
        self._btn_symbol.setStyleSheet(field_style())
        self._btn_symbol.clicked.connect(self._open_symbol_picker)
        grid.addWidget(self._btn_symbol, 0, 1)

        grid.addWidget(self._field_label("Timeframe:"), 1, 0)
        self._btn_interval = QPushButton()
        self._btn_interval.setObjectName("btnInterval")
        self._btn_interval.setFixedHeight(32)
        self._btn_interval.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_interval.setStyleSheet(field_style())
        self._btn_interval.clicked.connect(self._open_timeframe_picker)
        grid.addWidget(self._btn_interval, 1, 1)

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

        # EPIC-015 Phase 2: replaces `AppProgressBar` + a standalone Cancel
        # `QPushButton` — `ProgressBanner.qml` renders the caption, a bar
        # that actually shows its percent, and has its own Cancel button
        # built in, so there is nothing left for a sibling widget to add.
        self._progress_banner = ProgressBannerWidget()
        self._progress_banner.setFixedHeight(_PROGRESS_BANNER_HEIGHT)
        self._progress_banner.set_cancel_label(_CANCEL_LABEL)
        progress_layout.addWidget(self._progress_banner)

        layout.addWidget(self._progress_container)
        self._progress_container.setVisible(False)

        layout.addStretch()
        return card

    def _build_status_column(self) -> QVBoxLayout:
        """The status table itself (`DatabaseStatusPanel`, EPIC-015 Phase 2)
        is NOT built here — `_build_ui()` runs before a real view model
        exists to construct its `DatabaseStatusVM` from. `self._status_column`
        is kept so `set_view_model()` can `insertWidget(0, ..., 1)` the panel
        into this (otherwise empty) slot."""
        column = QVBoxLayout()
        self._status_column = column
        return column

    def _build_log_panel(self) -> AppLogPanel:
        """Now `PageShell`'s console band — same full-width placement below
        the workspace that Dev Board/Backtest already use, instead of being
        nested inside the status column's own width (its previous spot,
        inherited from when the rail sat to its left)."""
        self._log_panel = AppLogPanel("SYNC LOG")
        self._log_panel.setObjectName("syncLogPanel")
        self._log_panel.setMinimumHeight(190)
        return self._log_panel

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
