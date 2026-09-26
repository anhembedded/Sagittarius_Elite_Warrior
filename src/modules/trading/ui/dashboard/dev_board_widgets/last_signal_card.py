"""`BOT-144` — the Dev Board's Latest Signal card, split out of
`dev_board_panel.py`. `EPIC-023C` — mirrors
`TradingView._build_last_signal_card()`.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Panel

from ..dashboard_view_model import DashboardQmlViewModel
from .layout_helpers import section_row

_NO_SIGNAL_TEXT = "No signal yet."


class LastSignalCard(Panel):
    """Fully self-contained: reads only `view_model.strategy`, owns only
    its own label. Nothing outside this card ever reads `lbl_last_signal`
    directly (unlike the 16 attributes `dev_board_panel.py`'s own class
    docstring lists), so no pass-through property is needed."""

    def __init__(
        self, view_model: DashboardQmlViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        layout = self.body_layout
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(6)
        layout.addLayout(section_row("Latest Signal"))
        self._lbl_last_signal = QLabel(_NO_SIGNAL_TEXT)
        self._lbl_last_signal.setObjectName("lblLastSignal")
        self._lbl_last_signal.setWordWrap(True)
        layout.addWidget(self._lbl_last_signal)
        view_model.strategy.lastSignalChanged.connect(self._sync_last_signal)
        self._sync_last_signal()

    def _sync_last_signal(self) -> None:
        self._lbl_last_signal.setText(
            self._view_model.strategy.lastSignalText or _NO_SIGNAL_TEXT
        )
