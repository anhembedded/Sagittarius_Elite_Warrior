"""`BOT-144` — the Dev Board's Trading Session card, split out of
`dev_board_panel.py`. `EPIC-023D` — mirrors
`TradingView._build_session_card()`.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import (
    Panel,
    StyleRole,
    apply_role,
)

from ..dashboard_view_model import DashboardQmlViewModel
from .layout_helpers import field_label, section_row


class SessionCard(Panel):
    """Fully self-contained: reads only `view_model`, owns only its own two
    stat labels. Nothing outside this card ever reads them directly, so no
    pass-through property is needed."""

    def __init__(
        self, view_model: DashboardQmlViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self.setObjectName("devBoardSessionCard")
        layout = self.body_layout
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addLayout(section_row("Trading Session"))

        layout.addWidget(field_label("Orders Sent This Session"))
        self._lbl_orders_sent = QLabel("0")
        self._lbl_orders_sent.setObjectName("lblOrdersSentThisSession")
        apply_role(self._lbl_orders_sent, StyleRole.STAT_VALUE)
        layout.addWidget(self._lbl_orders_sent)

        layout.addWidget(field_label("Symbols With Open Positions"))
        self._lbl_open_symbols = QLabel("0")
        self._lbl_open_symbols.setObjectName("lblOpenSymbolsCount")
        apply_role(self._lbl_open_symbols, StyleRole.STAT_VALUE)
        layout.addWidget(self._lbl_open_symbols)

        view_model.sessionStatsChanged.connect(self._sync_session_stats)
        self._sync_session_stats()

    def _sync_session_stats(self) -> None:
        vm = self._view_model
        self._lbl_orders_sent.setText(str(vm.ordersSentThisSession))
        self._lbl_open_symbols.setText(str(vm.openSymbolsCount))
