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

`BOT-144` — the five cards (System Controls, Strategy, Last Signal, Session,
Manual Order) that used to be built and synced directly on this class now
live under `dev_board_widgets/`, each owning its own widgets and wiring.
This class keeps the header, the Indicators checklist (still entangled with
this panel's own script-catalog/symbol-preferences state), the dialogs a
card cannot parent itself, and the handful of cross-cutting syncs
(`_sync_controls_active`, `_sync_trading_state`) that reach into more than
one card or the header.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_catalog import (
    IndicatorScriptCatalog,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_params_store import (
    IndicatorScriptParamsStore,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_log_panel import (
    AppLogPanel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets import (
    Palette,
    get_icon_loader,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import (
    Panel,
    StyledButton,
    StyledCheckBox,
    StyleRole,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.symbol_picker import (
    SymbolPreferences,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.time_range_picker import (
    TimeRangePickerDialog,
)

from .dashboard_symbol_picker_dialog import DashboardSymbolPickerDialog
from .dashboard_view_model import DashboardQmlViewModel
from .dev_board_widgets.last_signal_card import LastSignalCard
from .dev_board_widgets.layout_helpers import section_row
from .dev_board_widgets.manual_order_card import ManualOrderCard
from .dev_board_widgets.session_card import SessionCard
from .dev_board_widgets.strategy_card import StrategyCard
from .dev_board_widgets.system_controls_card import (
    SystemControlsCallbacks,
    SystemControlsCard,
)
from .ws_status_pill import WsStatusPill

#: `DashboardQmlViewModel` (unlike `DataManagementViewModel`) exposes no
#: per-timeframe concept this panel can read — `startDate`/`endDate` are the
#: only range state it carries, and the active interval used by Load
#: History/Start Live lives on `DashboardPresenter._active_interval`, never
#: surfaced as a screen ViewModel property. The old `pick_date_range()`
#: bridge made the same "1m candle" assumption implicitly
#: (`_MINUTES_PER_DAY` in `components/date_range_picker.py`); this constant
#: keeps that behaviour, now named and documented instead of silent — and
#: derived from `TimeFrame.ONE_MINUTE` instead of a hand-computed `60` so the
#: two constants cannot silently drift apart from each other.
_FALLBACK_TIMEFRAME_SECONDS = TimeFrame.ONE_MINUTE.to_seconds()
_FALLBACK_TIMEFRAME_LABEL = TimeFrame.ONE_MINUTE.value

# --- `EPIC-023D` toggle/Emergency Stop — same fixed text `TradingView` uses. --- #
_TOGGLE_ON_TEXT = "Disable Trading"
_TOGGLE_OFF_TEXT = "Enable Trading"
_TOGGLE_BUSY_TEXT = "Processing..."
_EMERGENCY_STOP_TEXT = "EMERGENCY STOP"

#: Dock titles, one per card. A title is the user's handle on a panel — the
#: View menu lists it, a floating panel's title bar reads it, and
#: `QMainWindow.saveState()` keys the dock by it, so renaming one drops that
#: panel out of every perspective saved before the rename.
DATA_AND_STREAM_DOCK = "Data & stream"
STRATEGY_DOCK = "Strategy"
LAST_SIGNAL_DOCK = "Last signal"
SESSION_DOCK = "Session"
INDICATORS_DOCK = "Indicators"

#: The manual-order dialog's title, which is also how `WorkbenchSurface`
#: identifies it: `show_modal(MANUAL_ORDER_DIALOG)`.
MANUAL_ORDER_DIALOG = "Place order"


class DevBoardPanel(QObject):
    """The Dev Board's controls — everything that used to be
    `DevBoardPanel.qml`, then a scrolling column of cards in a `QSplitter`
    pane, and since `EPIC-025` PR 1.4c-3 **one card per dock**.

    It is no longer a widget, and that is the change: it builds the cards,
    owns every field and button, and wires them to the ViewModel, while
    *where they go* is `DashboardView`'s to decide — five docks the user can
    hide or tab independently, plus the manual-order card as a dialog. As a
    `QWidget` it had to be the region the cards sat on, which meant painting
    the app background with a stylesheet of its own (`Palette.BG`); a
    `QObject` paints nothing, and the workbench supplies the surface.

    Every private attribute stays where it was, because that is what the
    tests and the Presenter key off — `panel._btn_start`, `panel.
    _txt_start_date`, `panel._script_checkboxes`. What is new is the public
    read side: `dock_panels`, `manual_order_card`, `header_actions`,
    `status_tiles` and `console_widget`.
    """

    def __init__(
        self, view_model: DashboardQmlViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._symbol_picker: DashboardSymbolPickerDialog | None = None
        self._time_range_dialog: TimeRangePickerDialog | None = None
        # `BOT-063` — injected post-construction by `DashboardPresenter`
        # (`set_indicator_script_dependencies`), same "no container access
        # here" reasoning `set_symbol_preferences` gives; `None` until then
        # so a bare `DevBoardPanel(vm)` still builds, just with no working
        # params button.
        self._script_catalog: IndicatorScriptCatalog | None = None
        self._script_params_store: IndicatorScriptParamsStore | None = None
        # EPIC-014: replaced in production by the container-registered store
        # (`DashboardPresenter` injects it through `set_symbol_preferences`),
        # so a pair starred here is starred on Backtest too. Self-constructed
        # so a bare `DevBoardPanel(vm)` still opens a working picker; it just
        # remembers nothing past the session.
        self._symbol_preferences = SymbolPreferences()

        self._build_header_widgets()

        # Built here, kept on `self`, placed by `DashboardView`. Held by
        # reference and not by a layout: a `Panel()` with no parent and no
        # Python reference is garbage-collected the moment this method
        # returns, so the attribute *is* the ownership until a dock takes it.
        self._system_controls_card = SystemControlsCard(
            view_model,
            SystemControlsCallbacks(
                on_symbol_clicked=self._open_symbol_picker,
                on_pick_range=self._on_pick_range,
                on_start_date_edited=self._on_start_date_edited,
                on_end_date_edited=self._on_end_date_edited,
            ),
        )
        self._strategy_card = StrategyCard(view_model)
        self._last_signal_card = LastSignalCard(view_model)
        self._session_card = SessionCard(view_model)
        self._manual_order_card = ManualOrderCard(view_model)
        self._indicators_card = self._build_indicators()

        self._log_panel = AppLogPanel("SYSTEM MONITOR")
        self._log_panel.setObjectName("monitorLogPanel")
        self._log_panel.setMinimumHeight(160)
        self._log_panel.set_log_model(view_model.log_model)
        # Not added to `outer` — `DashboardView` places this in the
        # workbench's bottom dock instead (`console_widget` below), where it
        # spans the window and the user can hide it.

        self._wire_view_model()
        self._sync_price_ticker()
        self._sync_ws_status()
        self._sync_controls_active()
        self._sync_progress()
        self._sync_trading_state()

    # ------------------------------------------------------------------ #
    # System Controls card pass-through — the card owns these widgets;
    # `_sync_controls_active()` below (which also reaches the header's own
    # `_btn_reload`) and every existing test still read them as
    # `panel._btn_start` etc.
    # ------------------------------------------------------------------ #

    @property
    def _cbo_market(self) -> QWidget:
        return self._system_controls_card._cbo_market

    @property
    def _btn_symbol(self) -> QPushButton:
        return self._system_controls_card._btn_symbol

    @property
    def _txt_start_date(self) -> QWidget:
        return self._system_controls_card._txt_start_date

    @property
    def _txt_end_date(self) -> QWidget:
        return self._system_controls_card._txt_end_date

    @property
    def _btn_pick_range(self) -> QWidget:
        return self._system_controls_card._btn_pick_range

    @property
    def _btn_load_history(self) -> QWidget:
        return self._system_controls_card._btn_load_history

    @property
    def _btn_start(self) -> QWidget:
        return self._system_controls_card._btn_start

    @property
    def _btn_stop(self) -> QWidget:
        return self._system_controls_card._btn_stop

    @property
    def _progress_banner(self) -> QWidget:
        return self._system_controls_card._progress_banner

    # ------------------------------------------------------------------ #
    # Strategy/Manual Order card pass-through — same reasoning as the System
    # Controls block above. Found missing by a real GitHub Actions run
    # (`ci-local.ps1 -Full`, not the narrower local test selection this
    # split was first verified against): `tests/integration/presentation/ui/
    # test_dev_board_known_gaps.py`/`test_dev_board_manual_order_qt_click.py`
    # drive these widgets directly with real `qtbot` clicks, and were not
    # part of the grepped 16-attribute contract `BOT-144` §3.4 recorded
    # (that grep covered `test_dev_board_panel.py` and `DashboardView`/
    # `DashboardPresenter` only, not `tests/integration/`).
    # ------------------------------------------------------------------ #

    @property
    def _cbo_live_strategy(self) -> QWidget:
        return self._strategy_card._cbo_live_strategy

    @property
    def _cbo_live_interval(self) -> QWidget:
        return self._strategy_card._cbo_live_interval

    @property
    def _btn_arm_strategy(self) -> QWidget:
        return self._strategy_card._btn_arm_strategy

    @property
    def _lbl_armed_strategy(self) -> QWidget:
        return self._strategy_card._lbl_armed_strategy

    @property
    def _cbo_manual_order_type(self) -> QWidget:
        return self._manual_order_card._cbo_manual_order_type

    @property
    def _spn_manual_quantity(self) -> QWidget:
        return self._manual_order_card._spn_manual_quantity

    @property
    def _spn_manual_price(self) -> QWidget:
        return self._manual_order_card._spn_manual_price

    @property
    def _btn_manual_long(self) -> QWidget:
        return self._manual_order_card._btn_manual_long

    @property
    def _btn_manual_short(self) -> QWidget:
        return self._manual_order_card._btn_manual_short

    @property
    def _lbl_manual_order_status(self) -> QWidget:
        return self._manual_order_card._lbl_manual_order_status

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #

    def _build_header_widgets(self) -> None:
        """The price ticker, WS status pill, and the three buttons — no
        title, no wrapping row or `Panel` of their own. This panel is a dock,
        not the page header: `DashboardView` collects these through
        `header_actions` (the toolbar) and `status_tiles` (the status bar),
        the same split every other screen's View/content-panel pair uses."""
        self._price_ticker_label = QLabel()
        self._price_ticker_label.setObjectName("lblPriceTicker")

        # EPIC-015 Phase 4 — was a bare QLabel + colour-square QFrame, styled
        # inline via `_sync_ws_status()`; then `StatusPill.qml` embedded
        # inline. PR 4.3l makes it `WsStatusPill`, a dot and a label in this
        # screen's own package (ADR D21): it colours its own dot from
        # `semantic_colour()`, so nothing here styles it, and it measures
        # itself, so nothing here sizes it either.
        self._ws_status_pill = WsStatusPill()
        self._ws_status_pill.setObjectName("wsStatusPill")

        self._btn_reload = QPushButton()
        self._btn_reload.setObjectName("btnReload")
        self._btn_reload.setIcon(
            get_icon_loader().get_icon("clock", Palette.TEXT_PRIMARY, 12)
        )
        self._btn_reload.setFixedHeight(26)
        self._btn_reload.clicked.connect(self._view_model.requestLoadHistory)

        # `EPIC-023D` — same header placement `TradingView` gives its own
        # toggle button; Dev Board has no separate context bar for
        # "DỪNG KHẨN CẤP" the way Trading does, so it goes in `header_actions`
        # too, right beside the toggle — both must stay visible regardless
        # of which System Controls card state the panel is scrolled to.
        self._btn_toggle_trading = StyledButton(
            _TOGGLE_OFF_TEXT, role=StyleRole.PRIMARY_BUTTON
        )
        self._btn_toggle_trading.setObjectName("btnToggleTrading")
        self._btn_toggle_trading.setFixedHeight(26)
        self._btn_toggle_trading.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_toggle_trading.clicked.connect(self._view_model.requestToggle)

        self._btn_emergency_stop = StyledButton(
            _EMERGENCY_STOP_TEXT, role=StyleRole.DANGER_BUTTON
        )
        self._btn_emergency_stop.setObjectName("btnEmergencyStop")
        self._btn_emergency_stop.setFixedHeight(26)
        self._btn_emergency_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_emergency_stop.clicked.connect(self._view_model.requestEmergencyStop)

    @property
    def header_actions(self) -> list[QWidget]:
        """What `DashboardView` places in the workbench's header toolbar: the
        three things the user *does* from here.

        Mirrors `BackTestTopPanel.run_button`'s reason for existing — the
        private attributes stay what every existing test keys off. The price
        ticker and the websocket pill left this list in PR 1.4c-2: they report
        rather than act, and HLD §11.2 puts both in the status bar
        (`status_tiles` below).
        """
        return [
            self._btn_reload,
            self._btn_toggle_trading,
            self._btn_emergency_stop,
        ]

    @property
    def status_tiles(self) -> list[QWidget]:
        """What `DashboardView` places in the workbench's status bar: the two
        readouts that answer "is it live, and at what price" without the user
        asking for anything."""
        return [self._price_ticker_label, self._ws_status_pill]

    @property
    def console_widget(self) -> AppLogPanel:
        """Public accessor for `DashboardView` to place in the workbench's
        bottom dock."""
        return self._log_panel

    @property
    def dock_panels(self) -> list[tuple[str, QWidget]]:
        """`(dock title, card)` in the order they are offered to the
        workbench, which decides the initial tab order and nothing else —
        after that the user's perspective wins (HLD §11.2).

        Ordered by how often a user acts on them, the same ordering
        `TradingView._build_rail` documents for its own column: what you set
        up a run with, then what the run is doing, then what it did.
        """
        return [
            (DATA_AND_STREAM_DOCK, self._system_controls_card),
            (STRATEGY_DOCK, self._strategy_card),
            (LAST_SIGNAL_DOCK, self._last_signal_card),
            (SESSION_DOCK, self._session_card),
            (INDICATORS_DOCK, self._indicators_card),
        ]

    @property
    def manual_order_card(self) -> QWidget:
        """The manual-order form, for `DashboardView` to contribute as a
        dialog rather than a panel.

        A dialog because that is what order entry is: something the user
        does occasionally, with input and a confirmation, not something that
        must occupy the screen while they watch a chart (HLD §11.3, and
        MetaTrader's own F9). As a card in a scrolling column it was
        permanently in the way of everything below it.
        """
        return self._manual_order_card

    def _build_indicators(self) -> Panel:
        card = Panel()
        self._indicators_layout = card.body_layout
        self._indicators_layout.setContentsMargins(14, 14, 14, 14)
        self._indicators_layout.setSpacing(10)
        self._indicators_layout.addLayout(section_row("Indicators"))

        self._script_checkboxes: dict[str, StyledCheckBox] = {}
        #: `BOT-063` — only the scripts that declare `.inputs` get an entry.
        self._script_param_buttons: dict[str, QPushButton] = {}
        self._rebuild_script_rows()
        self._view_model.script_model.modelReset.connect(self._rebuild_script_rows)
        return card

    def _sync_trading_state(self) -> None:
        vm = self._view_model
        self._btn_toggle_trading.setEnabled(not vm.toggleBusy)
        if vm.toggleBusy:
            self._btn_toggle_trading.setText(_TOGGLE_BUSY_TEXT)
        else:
            self._btn_toggle_trading.setText(
                _TOGGLE_ON_TEXT if vm.enabled else _TOGGLE_OFF_TEXT
            )

    def set_indicator_script_dependencies(
        self,
        catalog: IndicatorScriptCatalog,
        store: IndicatorScriptParamsStore,
    ) -> None:
        """`BOT-063` — injected by `DashboardPresenter` (this panel has no
        container access), same reasoning `set_symbol_preferences` gives."""
        self._script_catalog = catalog
        self._script_params_store = store

    def set_symbol_preferences(self, preferences: SymbolPreferences) -> None:
        """Swaps in the shared, persisted favourites/recents store.

        @details Injected by `DashboardPresenter` (this panel has no
        container access), and forwards to an already-built picker so the order
        of construction and injection cannot matter. Until it is called the
        panel uses its own store, so a bare `DevBoardPanel(vm)` — every
        existing test — still opens a working picker.
        """
        if preferences is self._symbol_preferences:
            return
        self._symbol_preferences = preferences
        if self._symbol_picker is not None:
            self._symbol_picker.set_preferences(preferences)

    def _dialog_parent(self) -> QWidget:
        """The window a dialog this class opens should belong to.

        These two dialogs used to be parented to `self`, which worked while
        this class was a widget. It is a `QObject` since PR 1.4c-3, and a
        `QDialog` parented to one raises `TypeError` — found by the existing
        tests, not by reading. The window behind the button that opens it is
        the honest answer anyway: a dialog centres on its parent window, and
        the button is inside whichever dock the workbench put the card in.
        `window()` answers the button itself while nothing has placed the card
        yet, which is a valid parent and the case a bare
        `DevBoardPanel(view_model)` in a test is in.
        """
        return self._btn_symbol.window()

    def _open_symbol_picker(self) -> None:
        if self._symbol_picker is None:
            self._symbol_picker = DashboardSymbolPickerDialog(
                self._view_model,
                self._symbol_preferences,
                parent=self._dialog_parent(),
            )
            self._view_model.symbolOptionsChanged.connect(self._refresh_symbol_picker)
        # Emitted before showing, not after: the Presenter fetches on this
        # signal, and the dialog renders "Đang tải" until the list lands.
        self._view_model.symbolOptionsRequested.emit()
        self._symbol_picker.open_dialog()

    def _refresh_symbol_picker(self) -> None:
        if self._symbol_picker is not None and self._symbol_picker.isVisible():
            self._symbol_picker.refresh()

    # ------------------------------------------------------------------ #
    # Indicators checklist
    # ------------------------------------------------------------------ #

    def _rebuild_script_rows(self) -> None:
        while self._indicators_layout.count() > 1:
            item = self._indicators_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        self._script_checkboxes.clear()
        self._script_param_buttons.clear()

        model = self._view_model.script_model
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            key = model.data(index, model.KeyRole)
            title = model.data(index, model.TitleRole)
            enabled = bool(model.data(index, model.EnabledRole))
            has_params = bool(model.data(index, model.HasParamsRole))

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
            if has_params:
                # `BOT-063` — only a script that actually declares an
                # `input_*()` gets a params button; one that declares none
                # (`ema_cross`, `ema_ribbon`, the DEV showcase) has nothing
                # to edit.
                btn_params = QPushButton()
                btn_params.setObjectName(f"btnScriptParams_{key}")
                btn_params.setIcon(
                    get_icon_loader().get_icon("sliders", Palette.MUTED, 14)
                )
                btn_params.setFixedSize(24, 24)
                btn_params.setToolTip("Edit parameters")
                btn_params.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_params.clicked.connect(
                    lambda _checked=False, k=key: self._open_script_params_dialog(k)
                )
                self._script_param_buttons[key] = btn_params
                row_layout.addWidget(btn_params)
            self._indicators_layout.addWidget(row_frame)

    def _open_script_params_dialog(self, key: str) -> None:
        """Built fresh per opening, one per script key — see
        `IndicatorScriptParamsSink`'s own docstring for why this differs
        from a strategy card's one-permanent-sink shape. A no-op before the
        Presenter has injected the catalog/store
        (`set_indicator_script_dependencies`), same guard
        `_open_symbol_picker` gives for its own late-injected dependency."""
        if self._script_catalog is None or self._script_params_store is None:
            return
        from Sagittarius_Elite_Warrior.src.support.indicators.ui.script_params_sink import (
            IndicatorScriptParamsSink,
        )
        from Sagittarius_Elite_Warrior.src.support.ui_kit.param_form import (
            StrategyParamsDialog,
        )

        sink = IndicatorScriptParamsSink(
            self._script_catalog, self._script_params_store, key, parent=self
        )
        dialog = StrategyParamsDialog(
            sink, self._dialog_parent(), title="Indicator Parameters"
        )
        dialog.exec()

    # ------------------------------------------------------------------ #
    # ViewModel wiring
    # ------------------------------------------------------------------ #

    def _wire_view_model(self) -> None:
        vm = self._view_model
        vm.priceTickerChanged.connect(self._sync_price_ticker)
        vm.wsStatusChanged.connect(self._sync_ws_status)
        vm.historyLoadingChanged.connect(self._sync_controls_active)
        vm.uiModeChanged.connect(self._sync_controls_active)
        vm.progressChanged.connect(self._sync_progress)
        vm.startDateChanged.connect(self._sync_start_date)
        vm.endDateChanged.connect(self._sync_end_date)
        vm.symbolChanged.connect(self._sync_symbol)
        vm.tradingStateChanged.connect(self._sync_trading_state)

    def _on_start_date_edited(self, text: str) -> None:
        self._view_model.startDate = text

    def _on_pick_range(self) -> None:
        if self._time_range_dialog is None:
            self._time_range_dialog = TimeRangePickerDialog(
                get_from_text=lambda: self._txt_start_date.text(),
                get_to_text=lambda: self._txt_end_date.text(),
                get_timeframe_seconds=lambda: _FALLBACK_TIMEFRAME_SECONDS,
                get_timeframe_label=lambda: _FALLBACK_TIMEFRAME_LABEL,
                parent=self._dialog_parent(),
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
        `WsStatusPill` resolves its own colour given only the semantic
        `tone`, which `vm.wsStatusTone` already carries (set alongside
        text/color by the same `set_ws_status()` call, see
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
        # BOT-123 (was `vm.uiMode == "LIVE"` only): Start Live spends its
        # first several seconds — sometimes much longer, see the sync log
        # this was reported against — in LOCKED, syncing from Binance before
        # the websocket ever opens. Stop is how the user cancels that sync
        # (StreamLifecycleController._on_stop_stream cancels the same
        # CancellationToken the sync's cancellation_requested reads); leaving
        # it disabled through the one phase a user would most want to cancel
        # left LOCKED syncs with no way to stop short of killing the app.
        self._btn_stop.setEnabled(vm.uiMode in ("LIVE", "LOCKED"))
        self._cbo_market.setEnabled(controls_active)
        self._btn_symbol.setEnabled(controls_active)
        self._txt_start_date.setEnabled(controls_active)
        self._txt_end_date.setEnabled(controls_active)

    def _sync_progress(self) -> None:
        vm = self._view_model
        self._progress_banner.setVisible(vm.progressVisible)
        self._progress_banner.set_status_text(vm.progressText)
        self._progress_banner.set_indeterminate(vm.progressMaximum == 0)
        # `progressPercent` already computes and clamps value/maximum with a
        # `progressMaximum <= 0` guard (`DashboardQmlViewModel`) — reused
        # rather than re-deriving the same number here.
        self._progress_banner.set_percent(vm.progressPercent)
