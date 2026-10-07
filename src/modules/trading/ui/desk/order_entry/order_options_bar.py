"""`EPIC-028I` — the bar above the two sides: time in force on both desks;
reduce-only, the margin mode and the leverage on a desk with leverage
(`DeskProfile.futures_controls`).

@details The margin mode and leverage show the exchange's last answer, not
what was asked: choosing one asks the presenter (`OrderOptionsViewModel`'s
request signals), which sends `EPIC-028F`'s command and reads the symbol's
setting back. Until then the controls keep showing the previous setting.
Time in force applies to the resting orders (Limit, Stop-limit) only.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label

_TIME_IN_FORCE = (TimeInForce.GTC, TimeInForce.IOC, TimeInForce.FOK)
_MARGIN_TYPES = (MarginType.CROSSED, MarginType.ISOLATED)
_MARGIN_TEXT = {MarginType.CROSSED: "Cross", MarginType.ISOLATED: "Isolated"}
_RESTING = (OrderType.LIMIT, OrderType.STOP_LIMIT)
_MAX_LEVERAGE = 125


class OrderOptionsBar(QWidget):  # base-exempt: a container, not a surface
    """@brief How the panel's orders are sent."""

    def __init__(
        self, view_model: OrderEntryViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        options = view_model.options
        self._time_in_force = QComboBox()
        self._time_in_force.setObjectName("cboTimeInForce")
        self._time_in_force.setToolTip(
            "GTC rests until cancelled; IOC fills what it can at once; FOK "
            "fills completely at once or not at all"
        )
        for value in _TIME_IN_FORCE:
            self._time_in_force.addItem(value.value, value)
        self._time_in_force.activated.connect(
            lambda index: options.set_time_in_force(_TIME_IN_FORCE[index])
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(plain_label("TIF"))
        layout.addWidget(self._time_in_force)
        self._futures = view_model.profile.futures_controls
        if self._futures:
            self._add_futures_controls(layout)
        layout.addStretch(1)
        view_model.changed.connect(self.sync)
        self.sync()

    def _add_futures_controls(self, layout: QHBoxLayout) -> None:
        options = self._vm.options
        self._reduce_only = QCheckBox("Reduce-only")
        self._reduce_only.setObjectName("chkReduceOnly")
        self._reduce_only.setToolTip("Only close or shrink a position, never open one")
        self._reduce_only.toggled.connect(options.set_reduce_only)
        self._margin = QComboBox()
        self._margin.setObjectName("cboMarginType")
        for value in _MARGIN_TYPES:
            self._margin.addItem(_MARGIN_TEXT[value], value)
        self._margin.activated.connect(
            lambda index: options.request_margin_type(_MARGIN_TYPES[index])
        )
        self._leverage = QSpinBox()
        self._leverage.setObjectName("spnLeverage")
        self._leverage.setRange(1, _MAX_LEVERAGE)
        self._leverage.setSuffix("x")
        self._apply_leverage = QPushButton("Set")
        self._apply_leverage.setObjectName("btnSetLeverage")
        self._apply_leverage.setToolTip("Ask the exchange for this leverage")
        self._apply_leverage.clicked.connect(
            lambda: options.request_leverage(self._leverage.value())
        )
        for widget in (
            self._reduce_only,
            self._margin,
            self._leverage,
            self._apply_leverage,
        ):
            layout.addWidget(widget)

    def sync(self) -> None:
        vm = self._vm
        options = vm.options
        self._time_in_force.setCurrentIndex(_TIME_IN_FORCE.index(options.time_in_force))
        self._time_in_force.setEnabled(vm.order_type in _RESTING and not vm.busy)
        if not self._futures:
            return
        self._reduce_only.blockSignals(True)
        self._reduce_only.setChecked(options.reduce_only)
        self._reduce_only.blockSignals(False)
        setting = options.setting
        for widget in (self._margin, self._leverage, self._apply_leverage):
            widget.setEnabled(setting is not None and not vm.busy)
        if setting is not None:
            self._margin.setCurrentIndex(_MARGIN_TYPES.index(setting.margin_type))
            if not self._leverage.hasFocus():
                self._leverage.setValue(setting.leverage)
