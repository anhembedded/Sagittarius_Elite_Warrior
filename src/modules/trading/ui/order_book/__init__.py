"""The account's order book as the desktop renders it: two tables and a row
projection each (`EPIC-025` PR 1.4b-2).

Shared by Trading and the Dev Board, which is why it is a component and not a
screen's private widget — `EPIC-023A` had already moved the QML pair here for
that reason, and reaching into a sibling screen's directory is the
cross-screen-import anti-pattern `architecture-rule.md` §5 documents. The
destination for the whole package is `modules/trading/ui/`, in the phase where
the two screens follow it (HLD §3.5).
"""

from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.open_order_row import (
    OpenOrderRow,
    build_open_order_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.open_orders_panel import (
    OpenOrdersPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    PositionRow,
    build_position_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.positions_panel import (
    PositionsPanel,
)

__all__ = [
    "OpenOrderRow",
    "OpenOrdersPanel",
    "PositionRow",
    "PositionsPanel",
    "build_open_order_row",
    "build_position_row",
]
