"""`BOT-144` — the Dev Board's System Controls card, split out of
`dev_board_panel.py`. `BOT-123` — the `ProgressBanner` lets the user cancel
Start Live's `SyncMarketDataCommand` phase, the same `kit.ProgressBanner`
Backtest/Data Management already use.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QPushButton, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets import Palette, get_icon_loader
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Panel, ProgressBanner

from ..dashboard_view_model import DashboardQmlViewModel
from .layout_helpers import action_button_style, field_row, field_style, section_row


@dataclass(frozen=True)
class SystemControlsCallbacks:
    """Dialog management (the symbol picker, the date-range picker) needs a
    parent window and shared, presenter-injected state (`SymbolPreferences`)
    that only `DevBoardPanel` holds — see its own `_dialog_parent()`
    docstring. Bundled per `code/quality.md` §7 rather than passed as four
    separate constructor arguments."""

    on_symbol_clicked: Callable[[], None]
    on_pick_range: Callable[[], None]
    on_start_date_edited: Callable[[str], None]
    on_end_date_edited: Callable[[str], None]


class SystemControlsCard(Panel):
    """Everything else — the Market/Symbol fields, the date text fields, the
    Load History/Start/Stop actions and the progress banner — is
    self-contained on `view_model` alone. `_sync_controls_active()` (which
    also enables/disables the header's own `_btn_reload`) stays on
    `DevBoardPanel`, reading these widgets through the pass-through aliases
    every existing test already keys off."""

    def __init__(
        self,
        view_model: DashboardQmlViewModel,
        callbacks: SystemControlsCallbacks,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._callbacks = callbacks
        layout = self.body_layout
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        layout.addLayout(section_row("System Controls"))

        layout.addWidget(field_row("Market:", self._build_market_combo()))
        layout.addWidget(field_row("Symbol:", self._build_symbol_button()))

        layout.addLayout(section_row("Data Range"))

        self._txt_start_date = QLineEdit()
        self._txt_start_date.setObjectName("txtStartDate")
        self._txt_start_date.setPlaceholderText("yyyy-MM-dd HH:mm")
        self._txt_start_date.setFixedHeight(32)
        self._txt_start_date.setStyleSheet(field_style())
        self._txt_start_date.setText(view_model.startDate)
        self._txt_start_date.textEdited.connect(callbacks.on_start_date_edited)
        layout.addWidget(self._txt_start_date)

        self._txt_end_date = QLineEdit()
        self._txt_end_date.setObjectName("txtEndDate")
        self._txt_end_date.setPlaceholderText("yyyy-MM-dd HH:mm")
        self._txt_end_date.setFixedHeight(32)
        self._txt_end_date.setStyleSheet(field_style())
        self._txt_end_date.setText(view_model.endDate)
        self._txt_end_date.textEdited.connect(callbacks.on_end_date_edited)
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
        self._btn_pick_range.clicked.connect(callbacks.on_pick_range)
        pick_row.addWidget(self._btn_pick_range)
        layout.addLayout(pick_row)

        layout.addLayout(section_row("Actions"))

        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        self._btn_load_history = QPushButton()
        self._btn_load_history.setObjectName("btnLoadHistory")
        self._btn_load_history.setIcon(
            get_icon_loader().get_icon("clock", Palette.MUTED, 14)
        )
        self._btn_load_history.clicked.connect(view_model.requestLoadHistory)
        actions_row.addWidget(self._btn_load_history, 1)

        self._btn_start = QPushButton("Start Live")
        self._btn_start.setObjectName("btnStart")
        self._btn_start.setIcon(get_icon_loader().get_icon("play", Palette.SUCCESS, 14))
        self._btn_start.setStyleSheet(action_button_style(Palette.SUCCESS))
        self._btn_start.clicked.connect(view_model.requestStartStream)
        actions_row.addWidget(self._btn_start, 1)

        self._btn_stop = QPushButton("Stop")
        self._btn_stop.setObjectName("btnStop")
        self._btn_stop.setIcon(get_icon_loader().get_icon("square", Palette.DANGER, 14))
        self._btn_stop.setStyleSheet(action_button_style(Palette.DANGER))
        self._btn_stop.clicked.connect(view_model.requestStopStream)
        actions_row.addWidget(self._btn_stop, 1)

        layout.addLayout(actions_row)

        self._progress_banner = ProgressBanner()
        self._progress_banner.setObjectName("devBoardProgressBanner")
        self._progress_banner.setVisible(False)
        self._progress_banner.cancelRequested.connect(view_model.requestStopStream)
        layout.addWidget(self._progress_banner)

    def _build_market_combo(self) -> QComboBox:
        self._cbo_market = QComboBox()
        self._cbo_market.setObjectName("cboMarket")
        self._cbo_market.addItems(["Spot", "Futures"])
        self._cbo_market.setFixedHeight(32)
        self._cbo_market.setStyleSheet(field_style())
        return self._cbo_market

    def _build_symbol_button(self) -> QPushButton:
        """The field that opens the shared symbol picker.

        A button rather than a populated combo because the list is fetched
        on demand (it costs an exchange round trip) — see
        `DevBoardPanel._open_symbol_picker` for why opening it stays there.
        """
        self._btn_symbol = QPushButton(self._view_model.symbol)
        self._btn_symbol.setObjectName("btnSymbol")
        self._btn_symbol.setFixedHeight(32)
        self._btn_symbol.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_symbol.setStyleSheet(field_style())
        self._btn_symbol.clicked.connect(self._callbacks.on_symbol_clicked)
        return self._btn_symbol
