"""`BOT-144` — the Dev Board's Manual Order card, split out of
`dev_board_panel.py`. `EPIC-024B` — Long/Short submit directly, no separate
"submit" button: each is its own dispatch, same simplification this
feature's own task file allowed ("combo Long/Short (hoặc 2 nút tab)"). No
leverage/margin-mode field here — `PRO-003` §8.1 confirmed `ITradingClient`
has no way to change either on the real exchange, so drawing that control
would be a UI that lies (`domain-truth-rule.md`).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.manual_order_intent import (
    ManualOrderDirection,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets import Palette
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import (
    Panel,
    StyledButton,
    StyleRole,
)

from ..dashboard_view_model import DashboardQmlViewModel
from .layout_helpers import field_row, field_style, section_row

_MANUAL_ORDER_LONG_TEXT = "LONG"
_MANUAL_ORDER_SHORT_TEXT = "SHORT"


class ManualOrderCard(Panel):
    """Fully self-contained: reads only `view_model`, owns only its own
    fields. Nothing outside this card ever reads its widgets directly, so
    no pass-through property is needed — `dashboard_view.py` places the
    card itself as a dialog (`DevBoardPanel.manual_order_card`)."""

    def __init__(
        self, view_model: DashboardQmlViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self.setObjectName("devBoardManualOrderCard")
        layout = self.body_layout
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addLayout(section_row("Manual Order"))

        self._cbo_manual_order_type = QComboBox()
        self._cbo_manual_order_type.setObjectName("cboManualOrderType")
        self._cbo_manual_order_type.addItem("Market", OrderType.MARKET.name)
        self._cbo_manual_order_type.addItem("Limit", OrderType.LIMIT.name)
        self._cbo_manual_order_type.setFixedHeight(32)
        self._cbo_manual_order_type.setStyleSheet(field_style())
        self._cbo_manual_order_type.currentIndexChanged.connect(
            self._sync_manual_order_price_visibility
        )
        layout.addWidget(field_row("Order Type", self._cbo_manual_order_type))

        self._spn_manual_quantity = QDoubleSpinBox()
        self._spn_manual_quantity.setObjectName("spnManualQuantity")
        self._spn_manual_quantity.setDecimals(6)
        self._spn_manual_quantity.setRange(0.0, 1_000_000.0)
        self._spn_manual_quantity.setFixedHeight(32)
        self._spn_manual_quantity.setStyleSheet(field_style())
        layout.addWidget(field_row("Quantity", self._spn_manual_quantity))

        self._spn_manual_price = QDoubleSpinBox()
        self._spn_manual_price.setObjectName("spnManualPrice")
        self._spn_manual_price.setDecimals(2)
        self._spn_manual_price.setRange(0.0, 10_000_000.0)
        self._spn_manual_price.setFixedHeight(32)
        self._spn_manual_price.setStyleSheet(field_style())
        self._row_manual_price = field_row("Price (Limit)", self._spn_manual_price)
        layout.addWidget(self._row_manual_price)

        actions = QWidget()
        actions_row = QHBoxLayout(actions)
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.setSpacing(10)
        self._btn_manual_long = StyledButton(
            _MANUAL_ORDER_LONG_TEXT, role=StyleRole.PRIMARY_BUTTON
        )
        self._btn_manual_long.setObjectName("btnManualLong")
        self._btn_manual_long.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_manual_long.clicked.connect(
            lambda: self._on_manual_order_clicked(ManualOrderDirection.LONG)
        )
        self._btn_manual_short = StyledButton(
            _MANUAL_ORDER_SHORT_TEXT, role=StyleRole.DANGER_BUTTON
        )
        self._btn_manual_short.setObjectName("btnManualShort")
        self._btn_manual_short.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_manual_short.clicked.connect(
            lambda: self._on_manual_order_clicked(ManualOrderDirection.SHORT)
        )
        actions_row.addWidget(self._btn_manual_long)
        actions_row.addWidget(self._btn_manual_short)
        layout.addWidget(actions)

        self._lbl_manual_order_status = QLabel("")
        self._lbl_manual_order_status.setObjectName("lblManualOrderStatus")
        self._lbl_manual_order_status.setWordWrap(True)
        self._lbl_manual_order_status.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 11px;"
        )
        layout.addWidget(self._lbl_manual_order_status)

        #: Disabled together while a manual order attempt is in flight.
        self._manual_order_controls: tuple[QWidget, ...] = (
            self._cbo_manual_order_type,
            self._spn_manual_quantity,
            self._spn_manual_price,
            self._btn_manual_long,
            self._btn_manual_short,
        )
        view_model.manualOrderChanged.connect(self._sync_manual_order_state)
        self._sync_manual_order_price_visibility()
        self._sync_manual_order_state()

    def _sync_manual_order_price_visibility(self) -> None:
        order_type = OrderType[self._cbo_manual_order_type.currentData()]
        self._row_manual_price.setVisible(order_type is OrderType.LIMIT)

    def _sync_manual_order_state(self) -> None:
        vm = self._view_model
        for widget in self._manual_order_controls:
            widget.setEnabled(not vm.manualOrderBusy)
        # `DashboardQmlViewModel.manualOrderMessage` is a PySide6
        # `@Property(str)`; mypy reads the descriptor itself (`Property`)
        # rather than the `str` it actually holds at runtime — the same
        # systemic false positive `pyproject.toml`'s `[tool.mypy]` exclude
        # list documents for `presentation/` (needs a stub/plugin decision,
        # not a per-line fix).
        self._lbl_manual_order_status.setText(vm.manualOrderMessage)  # type: ignore[arg-type]

    def _on_manual_order_clicked(self, direction: ManualOrderDirection) -> None:
        order_type = OrderType[self._cbo_manual_order_type.currentData()]
        quantity = self._spn_manual_quantity.value()
        price = self._spn_manual_price.value() if order_type is OrderType.LIMIT else 0.0
        self._view_model.requestManualOrder(
            direction.value, quantity, order_type.name, price
        )
