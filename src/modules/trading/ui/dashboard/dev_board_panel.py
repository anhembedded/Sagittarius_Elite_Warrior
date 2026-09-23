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

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    MAX_LEVERAGE,
    MAX_SIZING_PERCENT,
    MIN_LEVERAGE,
    MIN_SIZING_PERCENT,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.manual_order_intent import (
    ManualOrderDirection,
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
    ProgressBanner,
    SectionLabel,
    StyledButton,
    StyledCheckBox,
    StyleRole,
    apply_role,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.symbol_picker import (
    SymbolPreferences,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.time_range_picker import (
    TimeRangePickerDialog,
)

from .dashboard_symbol_picker_dialog import DashboardSymbolPickerDialog
from .dashboard_view_model import DashboardQmlViewModel
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

# --- `EPIC-023C` strategy card — same fixed domain terms `TradingView`
# uses (`ui-presentation-rule.md`: "Strategy Parameters" is a fixed term,
# distinct from general Bot settings, never rephrased per screen). ---
_PARAMS_BUTTON_TEXT = "Strategy Parameters…"
_ARM_TEXT = "Arm Strategy"
_DISARM_TEXT = "Disarm"
_NOT_ARMED_TEXT = "No strategy armed."
_NO_SIGNAL_TEXT = "No signal yet."

# --- `EPIC-023D` toggle/Emergency Stop — same fixed text `TradingView` uses. --- #
_TOGGLE_ON_TEXT = "Disable Trading"
_TOGGLE_OFF_TEXT = "Enable Trading"
_TOGGLE_BUSY_TEXT = "Processing..."
_EMERGENCY_STOP_TEXT = "EMERGENCY STOP"

# --- `EPIC-024B` manual trading card. No leverage/margin-mode field here —
# `PRO-003` §8.1 confirmed `ITradingClient` has no way to change either on
# the real exchange, so drawing that control would be a UI that lies
# (`domain-truth-rule.md`). ---
_MANUAL_ORDER_LONG_TEXT = "LONG"
_MANUAL_ORDER_SHORT_TEXT = "SHORT"


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
        self._system_controls_card = self._build_system_controls()
        self._strategy_card = self._build_strategy_card()
        self._last_signal_card = self._build_last_signal_card()
        self._session_card = self._build_session_card()
        self._manual_order_card = self._build_manual_order_card()
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

    def _build_system_controls(self) -> Panel:
        card = Panel()
        layout = card.body_layout
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        layout.addLayout(_section_row("System Controls"))

        layout.addWidget(self._field_row("Market:", self._build_market_combo()))
        layout.addWidget(self._field_row("Symbol:", self._build_symbol_button()))

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
        self._btn_pick_range = QPushButton("Pick Dates")
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

        # BOT-123 — Start Live's `SyncMarketDataCommand` phase (fetching
        # missing candles from Binance before the websocket opens) used to
        # give no feedback at all: the log line "Syncing missing data from
        # Binance..." was the only sign anything was happening, for however
        # long that fetch took, with no way to cancel it short of killing
        # the app. Same `kit.ProgressBanner` Backtest/Data Management
        # already use, in the same spot relative to their own sync trigger.
        self._progress_banner = self._build_progress_banner()
        layout.addWidget(self._progress_banner)

        return card

    def _build_progress_banner(self) -> ProgressBanner:
        banner = ProgressBanner()
        banner.setObjectName("devBoardProgressBanner")
        banner.setVisible(False)
        banner.cancelRequested.connect(self._view_model.requestStopStream)
        return banner

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

    def _build_strategy_card(self) -> Panel:
        """`EPIC-023C` — a real "Nạp chiến lược" card, replacing the fake
        `_build_strategy_combo()` combo this screen used to carry (hard-coded
        `["Manual", "SMA Crossover"]`, never dispatching anything). Wiring
        mirrors `TradingView._build_strategy_card()` exactly — same fixed
        domain terms, same objectNames — driven by the same
        `StrategyArmingCoordinator` instance `DashboardPresenter` owns.

        `_sync_armed_summary()` disables the whole card while `strategyBusy`
        OR while trading is on (`EPIC-023D`) — the same pre-emptive,
        visible-before-click half of `EPIC-022` §4.1's rule `TradingView`'s
        own `_apply_armed_summary` enforces; the command handler refuses the
        swap server-side regardless either way.
        """
        card = Panel()
        layout = card.body_layout
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addLayout(_section_row("Strategy"))

        self._cbo_live_strategy = QComboBox()
        self._cbo_live_strategy.setObjectName("cboLiveStrategy")
        self._cbo_live_strategy.setFixedHeight(32)
        self._cbo_live_strategy.setStyleSheet(_field_style())
        layout.addWidget(self._field_row("Strategy", self._cbo_live_strategy))

        self._cbo_live_interval = QComboBox()
        self._cbo_live_interval.setObjectName("cboLiveInterval")
        self._cbo_live_interval.setFixedHeight(32)
        self._cbo_live_interval.setStyleSheet(_field_style())
        layout.addWidget(self._field_row("Timeframe", self._cbo_live_interval))

        self._spn_sizing_percent = QDoubleSpinBox()
        self._spn_sizing_percent.setObjectName("spnLiveSizingPercent")
        self._spn_sizing_percent.setRange(MIN_SIZING_PERCENT, MAX_SIZING_PERCENT)
        self._spn_sizing_percent.setSingleStep(1.0)
        self._spn_sizing_percent.setSuffix(" %")
        self._spn_sizing_percent.setFixedHeight(32)
        self._spn_sizing_percent.setStyleSheet(_field_style())
        layout.addWidget(self._field_row("% Capital/Trade", self._spn_sizing_percent))

        self._spn_leverage = QDoubleSpinBox()
        self._spn_leverage.setObjectName("spnLiveLeverage")
        self._spn_leverage.setRange(MIN_LEVERAGE, MAX_LEVERAGE)
        self._spn_leverage.setSingleStep(1.0)
        self._spn_leverage.setSuffix(" x")
        self._spn_leverage.setFixedHeight(32)
        self._spn_leverage.setStyleSheet(_field_style())
        layout.addWidget(self._field_row("Leverage", self._spn_leverage))

        self._btn_strategy_params = StyledButton(
            _PARAMS_BUTTON_TEXT, role=StyleRole.SECONDARY_BUTTON
        )
        self._btn_strategy_params.setObjectName("btnStrategyParams")
        self._btn_strategy_params.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self._btn_strategy_params)

        actions = QWidget()
        actions_row = QHBoxLayout(actions)
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.setSpacing(8)
        self._btn_arm_strategy = StyledButton(_ARM_TEXT, role=StyleRole.PRIMARY_BUTTON)
        self._btn_arm_strategy.setObjectName("btnArmStrategy")
        self._btn_arm_strategy.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_disarm_strategy = StyledButton(
            _DISARM_TEXT, role=StyleRole.SECONDARY_BUTTON
        )
        self._btn_disarm_strategy.setObjectName("btnDisarmStrategy")
        self._btn_disarm_strategy.setCursor(Qt.CursorShape.PointingHandCursor)
        actions_row.addWidget(self._btn_arm_strategy, 1)
        actions_row.addWidget(self._btn_disarm_strategy, 1)
        layout.addWidget(actions)

        self._lbl_armed_strategy = QLabel(_NOT_ARMED_TEXT)
        self._lbl_armed_strategy.setObjectName("lblArmedStrategy")
        self._lbl_armed_strategy.setWordWrap(True)
        layout.addWidget(self._lbl_armed_strategy)

        #: Everything above is disabled while an arm/disarm is in flight —
        #: see the docstring above for what this does NOT yet gate on.
        self._strategy_controls = (
            self._cbo_live_strategy,
            self._cbo_live_interval,
            self._spn_sizing_percent,
            self._spn_leverage,
            self._btn_strategy_params,
            self._btn_arm_strategy,
            self._btn_disarm_strategy,
        )

        self._cbo_live_strategy.currentIndexChanged.connect(
            lambda _index: self._view_model.strategy.requestStrategySelection(
                self._cbo_live_strategy.currentData() or ""
            )
        )
        self._cbo_live_interval.currentTextChanged.connect(
            self._view_model.strategy.requestIntervalSelection
        )
        self._spn_sizing_percent.valueChanged.connect(
            self._view_model.strategy.requestSizingPercent
        )
        self._spn_leverage.valueChanged.connect(
            self._view_model.strategy.requestLeverage
        )
        self._btn_arm_strategy.clicked.connect(self._view_model.strategy.requestArm)
        self._btn_disarm_strategy.clicked.connect(
            self._view_model.strategy.requestDisarm
        )
        self._btn_strategy_params.clicked.connect(self._open_strategy_params_dialog)

        self._view_model.strategy.strategyConfigChanged.connect(
            self._on_strategy_config_changed
        )
        self._sync_strategy_options()
        self._sync_strategy_selection()
        self._sync_armed_summary()

        return card

    def _build_last_signal_card(self) -> Panel:
        """`EPIC-023C` — mirrors `TradingView._build_last_signal_card()`."""
        card = Panel()
        layout = card.body_layout
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(6)
        layout.addLayout(_section_row("Latest Signal"))
        self._lbl_last_signal = QLabel(_NO_SIGNAL_TEXT)
        self._lbl_last_signal.setObjectName("lblLastSignal")
        self._lbl_last_signal.setWordWrap(True)
        layout.addWidget(self._lbl_last_signal)
        self._view_model.strategy.lastSignalChanged.connect(self._sync_last_signal)
        self._sync_last_signal()
        return card

    def _build_session_card(self) -> Panel:
        """`EPIC-023D` — mirrors `TradingView._build_session_card()`."""
        card = Panel()
        card.setObjectName("devBoardSessionCard")
        layout = card.body_layout
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addLayout(_section_row("Trading Session"))

        layout.addWidget(self._field_label("Orders Sent This Session"))
        self._lbl_orders_sent = QLabel("0")
        self._lbl_orders_sent.setObjectName("lblOrdersSentThisSession")
        apply_role(self._lbl_orders_sent, StyleRole.STAT_VALUE)
        layout.addWidget(self._lbl_orders_sent)

        layout.addWidget(self._field_label("Symbols With Open Positions"))
        self._lbl_open_symbols = QLabel("0")
        self._lbl_open_symbols.setObjectName("lblOpenSymbolsCount")
        apply_role(self._lbl_open_symbols, StyleRole.STAT_VALUE)
        layout.addWidget(self._lbl_open_symbols)

        self._sync_session_stats()
        return card

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 11px;")
        return label

    def _sync_session_stats(self) -> None:
        vm = self._view_model
        self._lbl_orders_sent.setText(str(vm.ordersSentThisSession))
        self._lbl_open_symbols.setText(str(vm.openSymbolsCount))

    def _sync_trading_state(self) -> None:
        vm = self._view_model
        self._btn_toggle_trading.setEnabled(not vm.toggleBusy)
        if vm.toggleBusy:
            self._btn_toggle_trading.setText(_TOGGLE_BUSY_TEXT)
        else:
            self._btn_toggle_trading.setText(
                _TOGGLE_ON_TEXT if vm.enabled else _TOGGLE_OFF_TEXT
            )
        # The strategy card's editable gate reads `vm.enabled` too
        # (`_sync_armed_summary`) — must re-run on every toggle, not just
        # on `strategyConfigChanged`, the same pairing `TradingView`'s own
        # `tradingStateChanged` connection documents.
        self._sync_armed_summary()

    # ------------------------------------------------------------------ #
    # Manual trading card (`EPIC-024B`) — Long/Short submit directly, no
    # separate "submit" button: each is its own dispatch, same simplification
    # this task's own file allows ("combo Long/Short (hoặc 2 nút tab)").
    # ------------------------------------------------------------------ #

    def _build_manual_order_card(self) -> Panel:
        card = Panel()
        card.setObjectName("devBoardManualOrderCard")
        layout = card.body_layout
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addLayout(_section_row("Manual Order"))

        self._cbo_manual_order_type = QComboBox()
        self._cbo_manual_order_type.setObjectName("cboManualOrderType")
        self._cbo_manual_order_type.addItem("Market", OrderType.MARKET.name)
        self._cbo_manual_order_type.addItem("Limit", OrderType.LIMIT.name)
        self._cbo_manual_order_type.setFixedHeight(32)
        self._cbo_manual_order_type.setStyleSheet(_field_style())
        self._cbo_manual_order_type.currentIndexChanged.connect(
            self._sync_manual_order_price_visibility
        )
        layout.addWidget(self._field_row("Order Type", self._cbo_manual_order_type))

        self._spn_manual_quantity = QDoubleSpinBox()
        self._spn_manual_quantity.setObjectName("spnManualQuantity")
        self._spn_manual_quantity.setDecimals(6)
        self._spn_manual_quantity.setRange(0.0, 1_000_000.0)
        self._spn_manual_quantity.setFixedHeight(32)
        self._spn_manual_quantity.setStyleSheet(_field_style())
        layout.addWidget(self._field_row("Quantity", self._spn_manual_quantity))

        self._spn_manual_price = QDoubleSpinBox()
        self._spn_manual_price.setObjectName("spnManualPrice")
        self._spn_manual_price.setDecimals(2)
        self._spn_manual_price.setRange(0.0, 10_000_000.0)
        self._spn_manual_price.setFixedHeight(32)
        self._spn_manual_price.setStyleSheet(_field_style())
        self._row_manual_price = self._field_row(
            "Price (Limit)", self._spn_manual_price
        )
        layout.addWidget(self._row_manual_price)

        actions = QWidget()
        actions_row = QHBoxLayout(actions)
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.setSpacing(10)
        self._btn_manual_long = StyledButton(
            _MANUAL_ORDER_LONG_TEXT, role=StyleRole.PRIMARY_BUTTON
        )
        self._btn_manual_long.setObjectName("btnManualLong")
        self._btn_manual_long.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_manual_long.clicked.connect(
            lambda: self._on_manual_order_clicked(ManualOrderDirection.LONG)
        )
        self._btn_manual_short = StyledButton(
            _MANUAL_ORDER_SHORT_TEXT, role=StyleRole.DANGER_BUTTON
        )
        self._btn_manual_short.setObjectName("btnManualShort")
        self._btn_manual_short.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_manual_short.clicked.connect(
            lambda: self._on_manual_order_clicked(ManualOrderDirection.SHORT)
        )
        actions_row.addWidget(self._btn_manual_long)
        actions_row.addWidget(self._btn_manual_short)
        layout.addWidget(actions)

        self._lbl_manual_order_status = QLabel("")
        self._lbl_manual_order_status.setObjectName("lblManualOrderStatus")
        self._lbl_manual_order_status.setWordWrap(True)
        self._lbl_manual_order_status.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 11px;"
        )
        layout.addWidget(self._lbl_manual_order_status)

        #: Disabled together while a manual order attempt is in flight —
        #: same "editable gate" idiom `_strategy_controls`/`_sync_armed_
        #: summary` uses above.
        self._manual_order_controls: tuple[QWidget, ...] = (
            self._cbo_manual_order_type,
            self._spn_manual_quantity,
            self._spn_manual_price,
            self._btn_manual_long,
            self._btn_manual_short,
        )
        self._sync_manual_order_price_visibility()
        self._sync_manual_order_state()
        return card

    def _sync_manual_order_price_visibility(self) -> None:
        order_type = OrderType[self._cbo_manual_order_type.currentData()]
        self._row_manual_price.setVisible(order_type is OrderType.LIMIT)

    def _sync_manual_order_state(self) -> None:
        vm = self._view_model
        for widget in self._manual_order_controls:
            widget.setEnabled(not vm.manualOrderBusy)
        self._lbl_manual_order_status.setText(vm.manualOrderMessage)

    def _on_manual_order_clicked(self, direction: ManualOrderDirection) -> None:
        order_type = OrderType[self._cbo_manual_order_type.currentData()]
        quantity = self._spn_manual_quantity.value()
        price = self._spn_manual_price.value() if order_type is OrderType.LIMIT else 0.0
        self._view_model.requestManualOrder(
            direction.value, quantity, order_type.name, price
        )

    def _open_strategy_params_dialog(self) -> None:
        """Built fresh per opening — same reasoning `TradingView`'s own
        method documents. Imported lazily for the same reason: the dialog
        pulls in `QScrollArea`/`Overlay` chrome no user who never opens it
        should pay for at panel construction.

        `BUG-134` — parents to `self._dialog_parent()`, never `self`:
        `DevBoardPanel` is a `QObject`, not a `QWidget` (`EPIC-025` PR
        1.4c-3), and a `QDialog` parented to one raises `TypeError` — see
        `_dialog_parent()`'s own docstring, which this call had not
        actually followed."""
        from Sagittarius_Elite_Warrior.src.support.ui_kit.param_form import (
            StrategyParamsDialog,
        )

        dialog = StrategyParamsDialog(self._view_model.strategy, self._dialog_parent())
        dialog.exec()

    def _on_strategy_config_changed(self) -> None:
        self._sync_strategy_options()
        self._sync_strategy_selection()
        self._sync_armed_summary()

    def _sync_strategy_options(self) -> None:
        """@details Each row's registry key rides on `setItemData`, never
        on the visible text — same reasoning `TradingView`'s own method
        documents (a renamed strategy silently stops being armable
        otherwise)."""
        self._cbo_live_strategy.blockSignals(True)
        self._cbo_live_strategy.clear()
        for option in self._view_model.strategy.strategyOptions:
            self._cbo_live_strategy.addItem(
                option.get("label", ""), option.get("key", "")
            )
        self._cbo_live_strategy.blockSignals(False)

        self._cbo_live_interval.blockSignals(True)
        self._cbo_live_interval.clear()
        self._cbo_live_interval.addItems(self._view_model.strategy.intervalOptions)
        self._cbo_live_interval.blockSignals(False)

    def _sync_strategy_selection(self) -> None:
        vm = self._view_model.strategy
        self._cbo_live_strategy.blockSignals(True)
        index = self._cbo_live_strategy.findData(vm.selectedStrategyKey)
        if index >= 0:
            self._cbo_live_strategy.setCurrentIndex(index)
        self._cbo_live_strategy.blockSignals(False)

        self._cbo_live_interval.blockSignals(True)
        if vm.liveInterval:
            self._cbo_live_interval.setCurrentText(vm.liveInterval)
        self._cbo_live_interval.blockSignals(False)

        for spin, value in (
            (self._spn_sizing_percent, vm.sizingPercent),
            (self._spn_leverage, vm.leverage),
        ):
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)

    def _sync_armed_summary(self) -> None:
        vm = self._view_model.strategy
        summary = vm.armedSummary
        self._lbl_armed_strategy.setText(summary or _NOT_ARMED_TEXT)
        self._lbl_armed_strategy.setStyleSheet(
            f"color: {Palette.SUCCESS if summary else Palette.MUTED}; font-size: 11px;"
        )
        # `EPIC-022` §4.1 — swapping the engine under an open position is
        # refused by the command handler too; this is the same rule made
        # visible before the click rather than after it (`TradingView`'s
        # own `_apply_armed_summary` docstring).
        editable = not vm.strategyBusy and not self._view_model.enabled
        for widget in self._strategy_controls:
            widget.setEnabled(editable)

    def _sync_last_signal(self) -> None:
        self._lbl_last_signal.setText(
            self._view_model.strategy.lastSignalText or _NO_SIGNAL_TEXT
        )

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
        vm.progressChanged.connect(self._sync_progress)
        vm.startDateChanged.connect(self._sync_start_date)
        vm.endDateChanged.connect(self._sync_end_date)
        vm.symbolChanged.connect(self._sync_symbol)
        vm.tradingStateChanged.connect(self._sync_trading_state)
        vm.sessionStatsChanged.connect(self._sync_session_stats)
        vm.manualOrderChanged.connect(self._sync_manual_order_state)

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
