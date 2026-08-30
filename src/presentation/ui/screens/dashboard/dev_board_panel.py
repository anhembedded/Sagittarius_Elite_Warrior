"""
@brief QtWidgets replacement for `DevBoardPanel.qml` (EPIC-006D): top status
bar, System Controls, Indicators checklist, and the System Monitor log.

@details
This screen used to keep eight of its own colour constants, and this
docstring used to defend them: it called them a deliberate "Live Testbed"
identity, distinct from `Palette`, and claimed the distinction had been
verified.

**That defence did not survive being checked** (`EPIC-007`, finding #3).
Five of the eight values were byte-identical to constants in
`backtest_top_panel.py`, a screen with no testbed identity to protect. Two screens holding the same private copy
of the same colour is not an identity; it is one copy-paste that nobody
went back to. The "verified" claim was about collisions with `Palette`, and
said nothing about collisions with each other, which is where they were.

So the constants are gone, and this screen reads `Palette` like every
other. The pixels did move — those five values sat a shade off the shared
tokens — and that was the accepted trade in `EPIC-007` §3.1: one token per
role, so changing a token changes every screen at once, which was the whole
promise `ui-architecture.md` §1 makes and could not keep while eight
private constants existed.

If this screen ever does want its own identity, the way to have one is a
named token in `Palette`, not a module constant a reader has to diff
against another file to discover is shared.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
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
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Panel,
    SectionLabel,
    StyledCheckBox,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.kit.status_pill_widget import (
    StatusPillWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TimeRangePicker.time_range_picker_dialog import (
    TimeRangePickerDialog,
)

from .dashboard_view_model import DashboardQmlViewModel

#: `DashboardQmlViewModel` (unlike `DataManagementViewModel`) exposes no
#: per-timeframe concept this panel can read — `startDate`/`endDate` are the
#: only range state it carries, and the active interval used by Load
#: History/Start Live lives on `DashboardPresenter._active_interval`, never
#: surfaced as a screen ViewModel property. The old `pick_date_range()`
#: bridge made the same "1m candle" assumption implicitly
#: (`_MINUTES_PER_DAY` in `components/date_range_picker.py`); this constant
#: keeps that behaviour, now named and documented instead of silent.
_FALLBACK_TIMEFRAME_SECONDS = 60
_FALLBACK_TIMEFRAME_LABEL = "1m"


def _field_style() -> str:
    return (
        f"background-color: {Palette.STATE_IDLE_BG}; color: {Palette.TEXT_PRIMARY}; "
        f"border: 1px solid {Palette.STATE_NAV_BORDER}; border-radius: 6px; padding: 0 10px;"
    )


def _section_row(title_text: str) -> QHBoxLayout:
    """A section heading in a row of its own.

    Was `_SectionLabel(QHBoxLayout)` — a heading that was an *arrangement*
    (a 3x12px tick `QFrame` beside a styled `QLabel`) rather than a thing,
    so it could not be styled, hidden or enabled as a unit. `EPIC-007F`
    replaces it with the engine's `SectionLabel`, whose tick is a QSS
    `border-left` on the label itself: one object where there were three.

    The wrapping row survives only because every call site pairs the
    heading with `addStretch(1)` to keep it left-aligned in a stretching
    column; the heading itself is now a widget.
    """
    row = QHBoxLayout()
    row.setSpacing(6)
    row.addWidget(SectionLabel(title_text, tick=True))
    row.addStretch(1)
    return row


class DevBoardPanel(QWidget):  # base-exempt: screen region on app bg, not a card
    """The right-hand panel of the Dev Board screen — everything that used
    to be `DevBoardPanel.qml`. `DashboardView` hosts this directly as a
    `QSplitter` child instead of a `QQuickWidget`.

    **Deliberately not a `Surface`/`Panel`**, unlike the three cards it
    contains. It paints the app background (`Palette.BG`) and draws no
    border of its own — it is the region the cards sit *on*, not one of
    them. Inheriting `Panel` would give it `BG_CARD` plus a border, i.e.
    a fourth card wrapped around the other three.
    """

    def __init__(
        self, view_model: DashboardQmlViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._symbol_picker: SymbolPickerOverlay | None = None
        self._time_range_dialog: TimeRangePickerDialog | None = None
        # EPIC-014: replaced in production by the container-registered store
        # (`DashboardPresenter` injects it through `set_symbol_preferences`),
        # so a pair starred here is starred on Backtest too. Self-constructed
        # so a bare `DevBoardPanel(vm)` still opens a working picker; it just
        # remembers nothing past the session.
        self._symbol_preferences = SymbolPreferences()
        # Scoped, not a bare property list: unscoped this would repaint
        # every descendant that has no rule of its own (`BUG-008`), which
        # here is most of the screen.
        self.setStyleSheet(
            f"{type(self).__name__} {{ background-color: {Palette.BG}; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(12)

        self._build_header_widgets()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # Scoped: unscoped, `border: none` would strip the border from every
        # descendant that does not set one of its own (`BUG-008`), and this
        # scroll area contains the whole card column.
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_body = QWidget()
        scroll_layout = QVBoxLayout(scroll_body)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(12)
        scroll_layout.addWidget(self._build_system_controls())
        scroll_layout.addWidget(self._build_indicators())
        scroll_layout.addStretch(1)
        scroll.setWidget(scroll_body)
        outer.addWidget(scroll, 1)

        self._log_panel = AppLogPanel("SYSTEM MONITOR")
        self._log_panel.setObjectName("monitorLogPanel")
        self._log_panel.setMinimumHeight(160)
        self._log_panel.set_log_model(view_model.log_model)
        # Not added to `outer` — `DashboardView` places this in `PageShell`'s
        # console band instead (`console_widget` below), the same full-width
        # placement every other screen's log uses.

        self._wire_view_model()
        self._sync_price_ticker()
        self._sync_ws_status()
        self._sync_controls_active()

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #

    def _build_header_widgets(self) -> None:
        """The price ticker, WS status pill, and Reload button — no title,
        no wrapping row/`Panel` of their own. This panel is the *rail* now,
        not the page header: the title text is `DashboardView`'s to own
        (`header_actions`/`console_widget` below are what it collects into
        `PageShell`'s header/console bands), the same split every other
        screen's View/content-panel pair already uses."""
        self._price_ticker_label = QLabel()
        self._price_ticker_label.setObjectName("lblPriceTicker")

        # EPIC-015 Phase 4 — was a bare QLabel + colour-square QFrame, styled
        # inline via `_sync_ws_status()`. Now `StatusPill.qml` embedded
        # inline (no modal, no `QmlOverlay` — see `StatusPillWidget`'s own
        # docstring): the pill draws its own rounded background/border/dot
        # from `Theme` tokens, so nothing here styles it.
        self._ws_status_pill = StatusPillWidget()
        self._ws_status_pill.setObjectName("wsStatusPill")
        self._ws_status_pill.setFixedHeight(22)

        self._btn_reload = QPushButton()
        self._btn_reload.setObjectName("btnReload")
        self._btn_reload.setIcon(
            get_icon_loader().get_icon("clock", Palette.TEXT_PRIMARY, 12)
        )
        self._btn_reload.setFixedHeight(26)
        self._btn_reload.clicked.connect(self._view_model.requestLoadHistory)

    @property
    def header_actions(self) -> list[QWidget]:
        """Public accessor for `DashboardView` to place in the page header —
        mirrors `BackTestTopPanel.run_button`'s reason for existing: the
        private attributes stay what every existing test keys off."""
        return [self._price_ticker_label, self._ws_status_pill, self._btn_reload]

    @property
    def console_widget(self) -> AppLogPanel:
        """Public accessor for `DashboardView` to place in `PageShell`'s
        console band."""
        return self._log_panel

    def _build_system_controls(self) -> Panel:
        card = Panel()
        layout = card.body_layout
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        layout.addLayout(_section_row("System Controls"))

        layout.addWidget(self._field_row("Market:", self._build_market_combo()))
        layout.addWidget(self._field_row("Symbol:", self._build_symbol_button()))
        layout.addWidget(self._field_row("Strategy:", self._build_strategy_combo()))

        layout.addLayout(_section_row("Data Range"))

        self._txt_start_date = QLineEdit()
        self._txt_start_date.setObjectName("txtStartDate")
        self._txt_start_date.setPlaceholderText("yyyy-MM-dd HH:mm")
        self._txt_start_date.setFixedHeight(32)
        self._txt_start_date.setStyleSheet(_field_style())
        self._txt_start_date.setText(self._view_model.startDate)
        self._txt_start_date.textEdited.connect(self._on_start_date_edited)
        layout.addWidget(self._txt_start_date)

        self._txt_end_date = QLineEdit()
        self._txt_end_date.setObjectName("txtEndDate")
        self._txt_end_date.setPlaceholderText("yyyy-MM-dd HH:mm")
        self._txt_end_date.setFixedHeight(32)
        self._txt_end_date.setStyleSheet(_field_style())
        self._txt_end_date.setText(self._view_model.endDate)
        self._txt_end_date.textEdited.connect(self._on_end_date_edited)
        layout.addWidget(self._txt_end_date)

        # Same bridge the storage screen uses: the two fields stay typable,
        # this only adds a calendar that writes into them.
        pick_row = QHBoxLayout()
        pick_row.setContentsMargins(0, 0, 0, 0)
        pick_row.addStretch(1)
        self._btn_pick_range = QPushButton("Chọn lịch")
        self._btn_pick_range.setObjectName("btnPickDataRange")
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

        layout.addLayout(_section_row("Actions"))

        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        self._btn_load_history = QPushButton()
        self._btn_load_history.setObjectName("btnLoadHistory")
        self._btn_load_history.setIcon(
            get_icon_loader().get_icon("clock", Palette.MUTED, 14)
        )
        self._btn_load_history.clicked.connect(self._view_model.requestLoadHistory)
        actions_row.addWidget(self._btn_load_history, 1)

        self._btn_start = QPushButton("Start Live")
        self._btn_start.setObjectName("btnStart")
        self._btn_start.setIcon(get_icon_loader().get_icon("play", Palette.SUCCESS, 14))
        self._btn_start.setStyleSheet(self._action_button_style(Palette.SUCCESS))
        self._btn_start.clicked.connect(self._view_model.requestStartStream)
        actions_row.addWidget(self._btn_start, 1)

        self._btn_stop = QPushButton("Stop")
        self._btn_stop.setObjectName("btnStop")
        self._btn_stop.setIcon(get_icon_loader().get_icon("square", Palette.DANGER, 14))
        self._btn_stop.setStyleSheet(self._action_button_style(Palette.DANGER))
        self._btn_stop.clicked.connect(self._view_model.requestStopStream)
        actions_row.addWidget(self._btn_stop, 1)

        layout.addLayout(actions_row)
        return card

    def _build_indicators(self) -> Panel:
        card = Panel()
        self._indicators_layout = card.body_layout
        self._indicators_layout.setContentsMargins(14, 14, 14, 14)
        self._indicators_layout.setSpacing(10)
        self._indicators_layout.addLayout(_section_row("Indicators"))

        self._script_checkboxes: dict[str, StyledCheckBox] = {}
        self._rebuild_script_rows()
        self._view_model.script_model.modelReset.connect(self._rebuild_script_rows)
        return card

    @staticmethod
    def _field_row(label_text: str, field: QWidget) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        label = QLabel(label_text)
        label.setFixedWidth(60)
        label.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 11px; font-weight: bold;"
        )
        layout.addWidget(label)
        layout.addWidget(field, 1)
        return row

    def _build_market_combo(self) -> QComboBox:
        self._cbo_market = QComboBox()
        self._cbo_market.setObjectName("cboMarket")
        self._cbo_market.addItems(["Spot", "Futures"])
        self._cbo_market.setFixedHeight(32)
        self._cbo_market.setStyleSheet(_field_style())
        return self._cbo_market

    def _build_symbol_button(self) -> QPushButton:
        """The field that opens the shared symbol picker.

        `EPIC-014`: was an editable `QComboBox` seeded with `["BTCUSDT",
        "ETHUSDT"]`. Two of the exchange's ~1,400 pairs were one click away
        and every other one had to be typed exactly, from memory, with
        nothing to validate it — a typo became a symbol the stream would
        never tick on. A button rather than a populated combo because the
        list is fetched on demand (it costs an exchange round trip), which is
        the same reason Backtest opens a dialog rather than filling a combo.
        """
        self._btn_symbol = QPushButton(self._view_model.symbol)
        self._btn_symbol.setObjectName("btnSymbol")
        self._btn_symbol.setFixedHeight(32)
        self._btn_symbol.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_symbol.setStyleSheet(_field_style())
        self._btn_symbol.clicked.connect(self._open_symbol_picker)
        return self._btn_symbol

    def set_symbol_preferences(self, preferences: SymbolPreferences) -> None:
        """Swaps in the shared, persisted favourites/recents store.

        @details Injected by `DashboardPresenter` (this panel has no
        container access), and rebinds an already-built picker so the order
        of construction and injection cannot matter. Until it is called the
        panel uses its own store, so a bare `DevBoardPanel(vm)` — every
        existing test — still opens a working picker.
        """
        if preferences is self._symbol_preferences:
            return
        if self._symbol_picker is not None:
            self._symbol_preferences.unbind_picker(
                self._symbol_picker, self._on_symbol_changed
            )
            preferences.bind_picker(self._symbol_picker, self._on_symbol_changed)
        self._symbol_preferences = preferences

    def _open_symbol_picker(self) -> None:
        if self._symbol_picker is None:
            self._symbol_picker = SymbolPickerOverlay(
                get_symbols=lambda: self._view_model.symbolOptions,
                get_favourites=lambda: self._symbol_preferences.favourites,
                get_recents=lambda: self._symbol_preferences.recents,
                get_current=lambda: self._view_model.symbol,
                parent=self,
            )
            self._symbol_preferences.bind_picker(
                self._symbol_picker, self._on_symbol_changed
            )
            self._view_model.symbolOptionsChanged.connect(self._refresh_symbol_picker)
        # Emitted before showing, not after: the Presenter fetches on this
        # signal, and the dialog renders "Đang tải" until the list lands.
        self._view_model.symbolOptionsRequested.emit()
        self._symbol_picker.show()
        self._symbol_picker.raise_()

    def _refresh_symbol_picker(self) -> None:
        if self._symbol_picker is not None and self._symbol_picker.isVisible():
            self._symbol_picker.refresh()

    def _build_strategy_combo(self) -> QComboBox:
        self._cbo_strategy = QComboBox()
        self._cbo_strategy.setObjectName("cboStrategy")
        self._cbo_strategy.addItems(["Manual", "SMA Crossover"])
        self._cbo_strategy.setFixedHeight(32)
        self._cbo_strategy.setStyleSheet(_field_style())
        return self._cbo_strategy

    @staticmethod
    def _action_button_style(accent: str) -> str:
        return (
            f"QPushButton {{ background-color: {Palette.STATE_IDLE_BG}; color: {Palette.TEXT_PRIMARY}; "
            f"border: 1px solid {accent}; border-radius: 6px; min-height: 32px; "
            f"font-size: 12px; }} "
            f"QPushButton:disabled {{ color: {Palette.MUTED}; border-color: {Palette.STATE_NAV_BORDER}; }}"
        )

    # ------------------------------------------------------------------ #
    # Indicators checklist
    # ------------------------------------------------------------------ #

    def _rebuild_script_rows(self) -> None:
        while self._indicators_layout.count() > 1:
            item = self._indicators_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        self._script_checkboxes.clear()

        model = self._view_model.script_model
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            key = model.data(index, model.KeyRole)
            title = model.data(index, model.TitleRole)
            enabled = bool(model.data(index, model.EnabledRole))

            checkbox = StyledCheckBox(title)
            checkbox.setObjectName(f"chkScript_{key}")
            checkbox.setChecked(enabled)
            checkbox.toggled.connect(
                lambda checked, r=row: self._view_model.script_model.setEnabled(
                    r, checked
                )
            )
            self._script_checkboxes[key] = checkbox

            # Row hover highlight — port of the QML delegate's
            # MouseArea.containsMouse-driven Rectangle background.
            row_frame = QFrame()
            row_frame.setFixedHeight(32)
            row_frame.setStyleSheet(
                f"QFrame {{ background-color: transparent; border-radius: 6px; }} "
                f"QFrame:hover {{ background-color: {Palette.STATE_HOVER_BG}; }}"
            )
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(8, 0, 8, 0)
            row_layout.addWidget(checkbox)
            row_layout.addStretch(1)
            self._indicators_layout.addWidget(row_frame)

    # ------------------------------------------------------------------ #
    # ViewModel wiring
    # ------------------------------------------------------------------ #

    def _wire_view_model(self) -> None:
        vm = self._view_model
        vm.priceTickerChanged.connect(self._sync_price_ticker)
        vm.wsStatusChanged.connect(self._sync_ws_status)
        vm.historyLoadingChanged.connect(self._sync_controls_active)
        vm.uiModeChanged.connect(self._sync_controls_active)
        vm.startDateChanged.connect(self._sync_start_date)
        vm.endDateChanged.connect(self._sync_end_date)
        vm.symbolChanged.connect(self._sync_symbol)

    def _on_start_date_edited(self, text: str) -> None:
        self._view_model.startDate = text

    def _on_pick_range(self) -> None:
        if self._time_range_dialog is None:
            self._time_range_dialog = TimeRangePickerDialog(
                get_from_text=lambda: self._txt_start_date.text(),
                get_to_text=lambda: self._txt_end_date.text(),
                get_timeframe_seconds=lambda: _FALLBACK_TIMEFRAME_SECONDS,
                get_timeframe_label=lambda: _FALLBACK_TIMEFRAME_LABEL,
                parent=self,
            )
            self._time_range_dialog.applied.connect(self._on_range_applied)
        self._time_range_dialog.open_dialog()

    def _on_range_applied(self, start: str, end: str) -> None:
        self._txt_start_date.setText(start)
        self._txt_end_date.setText(end)
        self._on_start_date_edited(start)
        self._on_end_date_edited(end)

    def _on_end_date_edited(self, text: str) -> None:
        self._view_model.endDate = text

    def _sync_start_date(self) -> None:
        if self._txt_start_date.text() != self._view_model.startDate:
            self._txt_start_date.setText(self._view_model.startDate)

    def _sync_end_date(self) -> None:
        if self._txt_end_date.text() != self._view_model.endDate:
            self._txt_end_date.setText(self._view_model.endDate)

    def _on_symbol_changed(self, text: str) -> None:
        if text.strip():
            self._view_model.symbol = text

    def _sync_symbol(self) -> None:
        """ViewModel → button label, the direction the other fields have.

        @details The old combo was seeded once in `_build_symbol_combo()` and
        never re-read, so anything that set `view_model.symbol` after
        construction left the widget showing a stale value. `EPIC-010D`
        restores a remembered symbol into the ViewModel, which made that gap
        reachable on every launch rather than rarely.

        `EPIC-014`'s button needs no `QSignalBlocker`: `setText()` emits
        nothing, so this direction can no longer write back into the
        ViewModel and look like the user acting (`EPIC-010` design D6/mode
        #12) — the hazard the blocker existed for is gone with the combo.
        """
        if self._btn_symbol.text() != self._view_model.symbol:
            self._btn_symbol.setText(self._view_model.symbol)

    def _sync_price_ticker(self) -> None:
        vm = self._view_model
        self._price_ticker_label.setText(vm.priceTickerText)
        self._price_ticker_label.setStyleSheet(
            f"color: {vm.priceTickerColor}; font-size: 13px; font-weight: bold;"
        )

    def _sync_ws_status(self) -> None:
        """`vm.wsStatusColor` (a raw hex string) is not read here at all —
        `StatusPill.qml` resolves its own colours from `Theme` given only
        the semantic `tone`, which `vm.wsStatusTone` already carries (set
        alongside text/color by the same `set_ws_status()` call, see
        `dashboard_view_model.py`)."""
        vm = self._view_model
        self._ws_status_pill.set_text(vm.wsStatusText)
        self._ws_status_pill.set_tone(vm.wsStatusTone)

    def _sync_controls_active(self) -> None:
        vm = self._view_model
        controls_active = vm.controlsEnabled and not vm.historyLoading
        self._btn_reload.setText("Loading…" if vm.historyLoading else "Reload")
        self._btn_reload.setEnabled(controls_active)
        self._btn_load_history.setText(
            "Loading…" if vm.historyLoading else "Load History"
        )
        self._btn_load_history.setEnabled(controls_active)
        self._btn_start.setEnabled(controls_active)
        self._btn_stop.setEnabled(vm.uiMode == "LIVE")
        self._cbo_market.setEnabled(controls_active)
        self._btn_symbol.setEnabled(controls_active)
        self._cbo_strategy.setEnabled(controls_active)
        self._txt_start_date.setEnabled(controls_active)
        self._txt_end_date.setEnabled(controls_active)
