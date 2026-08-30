from __future__ import annotations

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view_model import (
    DashboardQmlViewModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dev_board_panel import (
    DevBoardPanel,
)


def build_preview() -> QWidget:
    """Builds a standalone preview for the Dev Board panel."""
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
    panel.resize(420, 760)
    return panel
