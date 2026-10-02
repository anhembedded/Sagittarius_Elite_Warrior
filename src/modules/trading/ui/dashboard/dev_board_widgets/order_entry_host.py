"""`EPIC-028M` — the content of the Dev Board's F9 dialog: the desks' order
panel once the presenter hands it a view model, or a line saying why there is
none (no venue enabled, as a disabled desk says)."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_panel import (
    OrderEntryPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Panel


class OrderEntryHost(Panel):
    """@brief Holds the F9 dialog's one order panel, or its notice."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("devBoardOrderEntry")

    def attach(self, order: OrderEntryViewModel) -> None:
        """Shows the desks' order panel, bound to `order`."""
        self.body_layout.addWidget(OrderEntryPanel(order))

    def show_unavailable(self, text: str) -> None:
        """Says why the dialog holds no order panel."""
        notice = QLabel(text)
        notice.setObjectName("lblOrderEntryUnavailable")
        notice.setWordWrap(True)
        self.body_layout.addWidget(notice)
