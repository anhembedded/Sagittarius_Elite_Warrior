from PySide6 import QtCore, QtWidgets

from .chart_canvas_view import ChartDisplayMode

_MODE_LABELS: dict[ChartDisplayMode, str] = {
    ChartDisplayMode.OHLC: "Nến Nhật",
    ChartDisplayMode.EQUITY: "Đường Vốn",
    ChartDisplayMode.BOTH: "Song song",
}


class BacktestChartControls(QtWidgets.QWidget):
    """
    @brief Chart-area toolbar for the Backtest Screen: the 3-mode switch plus
    overlay toggles (BOT-056 §2.1/§2.2).

    @details Native `QtWidgets` (added to `ChartCard.add_to_header`, next to
    its existing `ChartToolbar`) rather than QML — this is purely "how do I
    look at data BackTestView already has", with no config to validate or
    dispatch, so it doesn't need the ViewModel/Presenter round-trip the rest
    of this screen uses for anything that reaches the engine. Dumb component,
    same rule `ChartToolbar` itself documents: emits signals, decides nothing.
    """

    sig_mode_changed = QtCore.Signal(str)  # ChartDisplayMode value
    sig_ema_toggled = QtCore.Signal(bool)
    sig_volume_toggled = QtCore.Signal(bool)
    sig_trade_flags_toggled = QtCore.Signal(bool)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._mode_buttons: dict[ChartDisplayMode, QtWidgets.QPushButton] = {}
        self._mode_group = QtWidgets.QButtonGroup(self)
        self._mode_group.setExclusive(True)
        for mode in ChartDisplayMode:
            btn = QtWidgets.QPushButton(_MODE_LABELS[mode])
            btn.setObjectName(f"btnChartMode_{mode.value}")
            btn.setCheckable(True)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            self._mode_group.addButton(btn)
            self._mode_buttons[mode] = btn
            layout.addWidget(btn)
        self._mode_buttons[ChartDisplayMode.OHLC].setChecked(True)
        self._mode_group.buttonClicked.connect(self._on_mode_button_clicked)

        layout.addSpacing(12)

        self._ema_check = self._add_checkbox(layout, "chkChartEma", "4 EMA")
        self._ema_check.setChecked(True)
        self._ema_check.toggled.connect(self.sig_ema_toggled.emit)

        self._volume_check = self._add_checkbox(layout, "chkChartVolume", "Volume")
        self._volume_check.setChecked(True)
        self._volume_check.toggled.connect(self.sig_volume_toggled.emit)

        self._trade_flags_check = self._add_checkbox(
            layout, "chkChartTradeFlags", "Buy/Sell Flags"
        )
        self._trade_flags_check.setChecked(True)
        self._trade_flags_check.toggled.connect(self.sig_trade_flags_toggled.emit)

        layout.addStretch(1)

    @staticmethod
    def _add_checkbox(
        layout: QtWidgets.QHBoxLayout, object_name: str, text: str
    ) -> QtWidgets.QCheckBox:
        check = QtWidgets.QCheckBox(text)
        check.setObjectName(object_name)
        layout.addWidget(check)
        return check

    def _on_mode_button_clicked(self, button: QtWidgets.QAbstractButton) -> None:
        for mode, mode_button in self._mode_buttons.items():
            if mode_button is button:
                self.sig_mode_changed.emit(mode.value)
                return

    def set_trade_flags_enabled(self, enabled: bool) -> None:
        """Buy/Sell flags are price-scale markers — meaningless once the
        main plot is showing Equity instead of price (see BackTestView's
        mode-render logic), so Equity-solo mode disables this control rather
        than silently drawing markers nobody asked to see."""
        self._trade_flags_check.setEnabled(enabled)

    def is_trade_flags_checked(self) -> bool:
        return self._trade_flags_check.isChecked()

    def set_ema_enabled(self, enabled: bool) -> None:
        """The 4 EMA overlay is price-scale too — left plotted through an
        Equity-solo switch, it stays on the same main plot as the equity
        curve and drags pyqtgraph's auto-range to the price axis (~tens of
        thousands), squashing the equity curve flat. Same treatment as
        `set_trade_flags_enabled`: disable the control, don't just leave the
        stale lines drawn."""
        self._ema_check.setEnabled(enabled)

    def is_ema_checked(self) -> bool:
        return self._ema_check.isChecked()
