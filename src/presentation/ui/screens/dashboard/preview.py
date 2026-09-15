from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view_model import (
    DashboardQmlViewModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dev_board_panel import (
    DevBoardPanel,
)


def build_preview() -> QWidget:
    """Builds a standalone preview of the Dev Board's control cards.

    `DevBoardPanel` is a `QObject` since `EPIC-025` PR 1.4c-3 — it builds the
    cards and the workbench places them in five docks and one dialog — so a
    preview has to do the placing itself. One column here, because a preview
    exists to show what the cards look like, not to reproduce the dock layout
    (`test_workbench_surface.py` covers that).
    """
    view_model = DashboardQmlViewModel()
    view_model.set_price_ticker(
        "ETHUSDT  3,241.55",
        "#26a69a",  # token-exempt: bull colour, matches chart_card/theme.py
    )
    view_model.set_ws_status(
        "WS: LIVE",
        "#26a69a",  # token-exempt: bull colour, matches chart_card/theme.py
        "success",
    )
    view_model.log_model.append("Prepared 1 charts.")
    view_model.log_model.append(
        "Live stream for ['ETHUSDT'] is running.", level="success"
    )
    view_model.script_model.set_available(
        {
            "ema_cross": type(
                "EmaCross", (), {"title": "EMA Crossover", "default_enabled": True}
            ),
            "rsi": type("Rsi", (), {"title": "RSI", "default_enabled": False}),
        }
    )

    panel = DevBoardPanel(view_model)

    host = QWidget()
    column = QVBoxLayout(host)
    for widget in (*panel.header_actions, *panel.status_tiles):
        column.addWidget(widget)
    for _title, card in panel.dock_panels:
        column.addWidget(card)
    column.addWidget(panel.manual_order_card)
    column.addWidget(panel.console_widget)
    # The preview owns the controller for as long as the widget lives: every
    # card and every signal connection belongs to it, and a `QObject` with no
    # reference left is collected the moment this function returns.
    host._dev_board_panel = panel
    host.resize(420, 760)
    return host
