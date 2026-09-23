from __future__ import annotations

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.watchlist.watchlist_view import (
    WatchlistView,
)


def build_preview() -> QWidget:
    """Builds a standalone preview for the Watchlist screen with a few
    seeded rows — some ticked, some still awaiting their first tick."""
    view = WatchlistView()
    view.model.set_symbols(["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"])
    view.model.update_tick("BTCUSDT", 65_432.10, 1.85, 12_345.67)
    view.model.update_tick("ETHUSDT", 3_210.55, -0.92, 45_678.90)
    view.resize(900, 600)
    return view
