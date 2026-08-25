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
from sagittarius_engine.extensions.pyside_mvc.widgets import (
    Panel,
    SectionLabel,
    StyledCheckBox,
)

from .dashboard_view_model import DashboardQmlViewModel


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
        # Scoped, not a bare property list: unscoped this would repaint
        # every descendant that has no rule of its own (`BUG-008`), which
        # here is most of the screen.
        self.setStyleSheet(
            f"{type(self).__name__} {{ background-color: {Palette.BG}; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(12)

        outer.addWidget(self._build_header())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
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
        outer.addWidget(self._log_panel)

        self._wire_view_model()
        self._sync_price_ticker()
        self._sync_ws_status()
        self._sync_controls_active()

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #

    def _build_header(self) -> Panel:
        bar = Panel()
        bar.setFixedHeight(44)
        # `Panel` already owns its own layout (`body_layout`), so content
        # goes *into* it rather than a second layout being installed on the
        # widget — Qt refuses the latter and leaves the content unparented.
        bar.body_layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(10)
        bar.body_layout.addLayout(row)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        tick = QFrame()
        tick.setFixedSize(3, 14)
        tick.setStyleSheet(f"background-color: {Palette.ACCENT}; border-radius: 2px;")
        title_row.addWidget(tick)
        title_label = QLabel("Developer Board (Live Testbed)")
        title_label.setObjectName("lblHeaderTitle")
        title_label.setFixedWidth(170)
        title_label.setStyleSheet(
            f"color: {Palette.TEXT_PRIMARY}; font-size: 13px; font-weight: bold;"
        )
        title_row.addWidget(title_label)
        row.addLayout(title_row)

        row.addStretch(1)

        self._price_ticker_label = QLabel()
        self._price_ticker_label.setObjectName("lblPriceTicker")
        row.addWidget(self._price_ticker_label)

        ws_badge = QFrame()
        ws_badge.setFixedHeight(22)
        ws_badge.setStyleSheet(
            f"background-color: {Palette.BG_CARD_HEADER}; border: 1px solid {Palette.STATE_NAV_BORDER}; "
            f"border-radius: 11px;"
        )
        badge_row = QHBoxLayout(ws_badge)
        badge_row.setContentsMargins(10, 0, 10, 0)
        badge_row.setSpacing(6)
        self._ws_dot = QFrame()
        self._ws_dot.setFixedSize(6, 6)
        badge_row.addWidget(self._ws_dot)
        self._ws_status_label = QLabel()
        self._ws_status_label.setObjectName("lblWsStatus")
        badge_row.addWidget(self._ws_status_label)
        row.addWidget(ws_badge)

        self._btn_reload = QPushButton()
        self._btn_reload.setObjectName("btnReload")
        self._btn_reload.setIcon(
            get_icon_loader().get_icon("clock", Palette.TEXT_PRIMARY, 12)
        )
        self._btn_reload.setFixedHeight(26)
        self._btn_reload.clicked.connect(self._view_model.requestLoadHistory)
        row.addWidget(self._btn_reload)

        return bar

    def _build_system_controls(self) -> Panel:
        card = Panel()
        layout = card.body_layout
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        layout.addLayout(_section_row("System Controls"))

        layout.addWidget(self._field_row("Market:", self._build_market_combo()))
        layout.addWidget(self._field_row("Symbol:", self._build_symbol_combo()))
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

    def _build_symbol_combo(self) -> QComboBox:
        self._cbo_symbol = QComboBox()
        self._cbo_symbol.setObjectName("cboSymbol")
        self._cbo_symbol.setEditable(True)
        self._cbo_symbol.addItems(["BTCUSDT", "ETHUSDT"])
        self._cbo_symbol.setFixedHeight(32)
        self._cbo_symbol.setStyleSheet(_field_style())
        self._cbo_symbol.setCurrentText(self._view_model.symbol)
        self._cbo_symbol.currentTextChanged.connect(self._on_symbol_changed)
        return self._cbo_symbol

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

    def _on_start_date_edited(self, text: str) -> None:
        self._view_model.startDate = text

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

    def _sync_price_ticker(self) -> None:
        vm = self._view_model
        self._price_ticker_label.setText(vm.priceTickerText)
        self._price_ticker_label.setStyleSheet(
            f"color: {vm.priceTickerColor}; font-size: 13px; font-weight: bold;"
        )

    def _sync_ws_status(self) -> None:
        vm = self._view_model
        self._ws_status_label.setText(vm.wsStatusText)
        self._ws_status_label.setStyleSheet(
            f"color: {vm.wsStatusColor}; font-size: 10px; font-weight: bold;"
        )
        self._ws_dot.setStyleSheet(
            f"background-color: {vm.wsStatusColor}; border-radius: 3px;"
        )

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
        self._cbo_symbol.setEnabled(controls_active)
        self._cbo_strategy.setEnabled(controls_active)
        self._txt_start_date.setEnabled(controls_active)
        self._txt_end_date.setEnabled(controls_active)
