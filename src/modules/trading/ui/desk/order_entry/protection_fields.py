"""`EPIC-028I` — one side's take-profit and stop-loss fields, shown while
the panel's TP/SL box is on.

@details Each is a trigger price; the orders are placed once the entry
fills (`ProtectiveOrderFollower`). A field writes to the options view model
and is only rewritten when the model's value differs, as the side's other
fields are.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLineEdit, QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.amount_text import (
    format_amount,
    parse_amount,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_options_view_model import (
    OrderOptionsViewModel,
)


class ProtectionFields(QWidget):  # base-exempt: a container, not a surface
    """@brief One side's TP and SL trigger prices."""

    def __init__(
        self,
        options: OrderOptionsViewModel,
        side: EntrySide,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._options = options
        self._side = side
        name = side.value.capitalize()
        self._take_profit = QLineEdit()
        self._take_profit.setObjectName(f"txtTakeProfit{name}")
        self._take_profit.setPlaceholderText("Take-profit trigger")
        self._take_profit.textEdited.connect(
            lambda text: options.set_take_profit(side, text)
        )
        self._stop_loss = QLineEdit()
        self._stop_loss.setObjectName(f"txtStopLoss{name}")
        self._stop_loss.setPlaceholderText("Stop-loss trigger")
        self._stop_loss.textEdited.connect(
            lambda text: options.set_stop_loss(side, text)
        )
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addRow("TP", self._take_profit)
        layout.addRow("SL", self._stop_loss)
        options.changed.connect(self.sync)
        self.sync()

    def sync(self) -> None:
        self.setVisible(self._options.tp_sl_enabled)
        levels = self._options.protection(self._side)
        for field, value in (
            (self._take_profit, levels.take_profit if levels else None),
            (self._stop_loss, levels.stop_loss if levels else None),
        ):
            if parse_amount(field.text()) != value:
                field.setText("" if value is None else format_amount(value))
