"""`BOT-144` — the Dev Board's Trading Session card, split out of
`dev_board_panel.py`. `EPIC-023D` — mirrored the Trading screen's session
card (retired in `EPIC-028M`). `EPIC-033N` — its two figures are the
Engine's `ReadoutForm`, written by the application's formatter, instead of a
caption and a styled stat label each.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Panel
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    APP_VALUE_FORMATTER,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    ReadoutForm,
)

from ..dashboard_view_model import DashboardQmlViewModel
from .layout_helpers import section_row

_FIGURES = (
    ColumnSpec("orders_sent", "Orders sent this session", ColumnKind.QUANTITY),
    ColumnSpec("open_symbols", "Symbols with open positions", ColumnKind.QUANTITY),
)


class SessionCard(Panel):
    """Fully self-contained: reads only `view_model`, owns only its own
    read-out. Nothing outside this card reads it except through `figures`."""

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

        self.figures = ReadoutForm(_FIGURES, APP_VALUE_FORMATTER)
        self.figures.setObjectName("roDevBoardSession")
        layout.addWidget(self.figures)

        view_model.sessionStatsChanged.connect(self._sync_session_stats)
        self._sync_session_stats()

    def _sync_session_stats(self) -> None:
        vm = self._view_model
        # PySide6 `@Property` fields: mypy reads the descriptor, not the `int`
        # it holds — the false positive `last_signal_card.py` documents.
        orders_sent: int = vm.ordersSentThisSession  # type: ignore[assignment]
        open_symbols: int = vm.openSymbolsCount  # type: ignore[assignment]
        self.figures.set_values(
            {"orders_sent": orders_sent, "open_symbols": open_symbols}
        )
