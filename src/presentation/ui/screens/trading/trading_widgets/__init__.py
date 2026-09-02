"""QtWidgets building blocks for the Trading screen (`EPIC-021I`), each
embedding a shared `qml/*Table` component. Kept in their own module so
`trading_view.py` stays about assembly, not QQuickWidget construction —
same split `data_management_widgets/` uses.
"""

from __future__ import annotations

from .open_orders_panel import OpenOrdersPanel
from .positions_panel import PositionsPanel

__all__ = [
    "OpenOrdersPanel",
    "PositionsPanel",
]
