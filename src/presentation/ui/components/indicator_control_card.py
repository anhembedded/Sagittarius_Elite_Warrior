from PySide6.QtWidgets import QCheckBox, QFormLayout, QGroupBox, QSpinBox

from Binace_Bot.src.presentation.ui.components.base_card import BaseCard

_MIN_PERIOD = 2
_MAX_PERIOD = 200
_DEFAULT_RSI_PERIOD = 14
_DEFAULT_EMA_PERIOD = 20


class IndicatorControlCard(BaseCard):
    """
    @brief Lets the user enable/disable RSI, EMA, and MACD and set their
    periods, for display on the Dev Board's chart.
    @details Inherits from BaseCard. Follows Rule 1: No DB imports, no
    business logic — exposes plain Qt widgets for the Presenter to read
    (matching the existing `chk_custom_time`/`dt_from` convention in
    SyncControlCard), and never constructs domain Indicator instances
    itself.
    """

    def __init__(self, parent=None):
        super().__init__(title="Indicators", parent=parent)
        self._setup_content()

    def _setup_content(self):
        group_rsi = QGroupBox()
        layout_rsi = QFormLayout(group_rsi)
        self.chk_rsi = QCheckBox("RSI")
        self.spin_rsi_period = QSpinBox()
        self.spin_rsi_period.setRange(_MIN_PERIOD, _MAX_PERIOD)
        self.spin_rsi_period.setValue(_DEFAULT_RSI_PERIOD)
        layout_rsi.addRow(self.chk_rsi)
        layout_rsi.addRow("Period:", self.spin_rsi_period)

        group_ema = QGroupBox()
        layout_ema = QFormLayout(group_ema)
        self.chk_ema = QCheckBox("EMA")
        self.spin_ema_period = QSpinBox()
        self.spin_ema_period.setRange(_MIN_PERIOD, _MAX_PERIOD)
        self.spin_ema_period.setValue(_DEFAULT_EMA_PERIOD)
        layout_ema.addRow(self.chk_ema)
        layout_ema.addRow("Period:", self.spin_ema_period)

        group_macd = QGroupBox()
        layout_macd = QFormLayout(group_macd)
        self.chk_macd = QCheckBox("MACD (12/26/9)")
        layout_macd.addRow(self.chk_macd)

        self.body_layout.addWidget(group_rsi)
        self.body_layout.addWidget(group_ema)
        self.body_layout.addWidget(group_macd)
        self.body_layout.addStretch()
