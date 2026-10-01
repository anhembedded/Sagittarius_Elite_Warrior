"""`EPIC-028H` — `SideLayout.TWO_COLUMNS`: a Buy form and a Sell form side
by side, each with its own price and amount (the Spot desk)."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_side_form import (
    OrderSideForm,
)


class TwoColumnSides(QWidget):  # base-exempt: a container, not a surface
    """@brief One `OrderSideForm` per side, in two columns."""

    def __init__(
        self, view_model: OrderEntryViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.forms = {side: OrderSideForm(view_model, side) for side in EntrySide}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for side in EntrySide:
            layout.addWidget(self.forms[side], 1)
