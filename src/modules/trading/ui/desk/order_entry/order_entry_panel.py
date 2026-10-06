"""`EPIC-028H` — the order-entry panel: the order-type tabs, the sides laid
out as the desk's profile says, and one status line.

@details The core is the same on both desks; `DeskProfile.side_layout`
picks the layout from `_SIDE_LAYOUTS`, so a new desk adds one entry there
and never a branch here (ADR D5). Every order type the profile offers gets a
tab, so a desk offers Stop-limit (`EPIC-028O`) by listing it in its profile,
never by a branch here. The TP/SL toggle is the one
exception, by ADR O2: it is drawn on every desk and disabled, with the
reason as its tooltip, where the desk cannot place protective orders.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QTabBar,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    SideLayout,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_confirmation import (
    ConfirmOrder,
    OrderConfirmation,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_options_bar import (
    OrderOptionsBar,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.two_column_sides import (
    TwoColumnSides,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.verb_confirmation import (
    VerbQuestion,
    ask_with_verbs,
)

_TAB_TEXT = {
    OrderType.LIMIT: "Limit",
    OrderType.MARKET: "Market",
    OrderType.STOP_LIMIT: "Stop-limit",
}

#: Each layout offers `first_field`, where New order… (F9) puts the focus.
_SIDE_LAYOUTS: dict[SideLayout, Callable[[OrderEntryViewModel], TwoColumnSides]] = {
    SideLayout.TWO_COLUMNS: TwoColumnSides,
}


def confirm_with_message_box(parent: QWidget) -> ConfirmOrder:
    """@return The real dialog: Place order sends the order, Cancel (the
    default, and Esc) does not (`ui-presentation-rule.md` §10)."""

    def ask(confirmation: OrderConfirmation) -> bool:
        return ask_with_verbs(
            parent,
            VerbQuestion(
                title=confirmation.title.title(),
                question=confirmation.question,
                act="Place order",
                keep="Cancel",
                details=confirmation.details,
            ),
        )

    return ask


class OrderEntryPanel(QWidget):  # base-exempt: a container, not a surface
    """@brief One desk's order panel."""

    def __init__(
        self, view_model: OrderEntryViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("orderEntryPanel")
        self._vm = view_model
        self._order_types = view_model.profile.order_types
        self._tabs = QTabBar()
        self._tabs.setObjectName("tabOrderType")
        for order_type in self._order_types:
            self._tabs.addTab(_TAB_TEXT[order_type])
        self._tabs.currentChanged.connect(
            lambda index: view_model.set_order_type(self._order_types[index])
        )
        self._tp_sl = QCheckBox("TP/SL")
        self._tp_sl.setObjectName("chkTpSl")
        reason = view_model.profile.tp_sl_unavailable_reason
        self._tp_sl.setToolTip(
            reason or "Place a take-profit and a stop-loss once the entry fills"
        )
        self._tp_sl_available = reason is None
        self._tp_sl.toggled.connect(view_model.options.set_tp_sl_enabled)
        self._options = OrderOptionsBar(view_model)
        self.sides = _SIDE_LAYOUTS[view_model.profile.side_layout](view_model)
        self._status = QLabel()
        self._status.setObjectName("lblOrderEntryStatus")
        self._status.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs)
        layout.addWidget(self._options)
        layout.addWidget(self._tp_sl)
        layout.addWidget(self.sides, 1)
        layout.addWidget(self._status)
        view_model.changed.connect(self._sync)
        view_model.focusRequested.connect(self._focus_first_field)
        self._sync()

    def _focus_first_field(self) -> None:
        field = self.sides.first_field()
        if field is not None:
            field.setFocus(Qt.FocusReason.ShortcutFocusReason)
            field.selectAll()

    def _sync(self) -> None:
        vm = self._vm
        self._tabs.blockSignals(True)
        self._tabs.setCurrentIndex(self._order_types.index(vm.order_type))
        self._tabs.blockSignals(False)
        self._tabs.setEnabled(not vm.busy)
        self._tp_sl.setEnabled(self._tp_sl_available and not vm.busy)
        prefix = "Error: " if vm.message_is_error and vm.message else ""
        self._status.setText(f"{prefix}{vm.message}")
