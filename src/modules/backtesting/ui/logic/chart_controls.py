from PySide6 import QtCore, QtWidgets
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels

from .chart_canvas_view import ChartDisplayMode, MarkerOutcomeFilter, MarkerSideFilter

_MODE_LABELS = EnumLabels(
    ChartDisplayMode,
    {
        ChartDisplayMode.OHLC: "Candlestick",
        ChartDisplayMode.EQUITY: "Equity Curve",
        ChartDisplayMode.BOTH: "Side by Side",
    },
)

_OUTCOME_LABELS = EnumLabels(
    MarkerOutcomeFilter,
    {
        MarkerOutcomeFilter.ALL: "All",
        MarkerOutcomeFilter.WINS_ONLY: "Wins Only",
        MarkerOutcomeFilter.LOSSES_ONLY: "Losses Only",
    },
)

_SIDE_LABELS = EnumLabels(
    MarkerSideFilter,
    {
        MarkerSideFilter.ALL: "All",
        MarkerSideFilter.LONG_ONLY: "Long Only",
        MarkerSideFilter.SHORT_ONLY: "Short Only",
    },
)

#: PROP-004's own AC-3 caps how much a marker filter's own% threshold can
#: hide — 100% would let one control blank the chart along with the
#: trade-flags checkbox already doing that job, which is no longer "filter".
_MAX_MIN_PNL_PERCENT = 99.0


class BacktestChartControls(QtWidgets.QWidget):
    """
    @brief Chart-area toolbar for the Backtest Screen: the 3-mode switch plus
    overlay toggles (BOT-056 §2.1/§2.2).

    @details Native `QtWidgets` (added via `ChartCard.add_to_header`, next to
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
    #: PROP-004 — one signal for all 3 marker-filter controls (outcome/side/
    #: min-PnL), the same "no config to validate or dispatch" reasoning this
    #: class's own docstring gives for the toggles above: a listener just
    #: re-reads the 3 getters below and redraws, so 3 separately-typed
    #: signals would buy nothing a single no-payload one doesn't already do.
    sig_marker_filter_changed = QtCore.Signal()

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

        # BOT-060: no longer a fixed "4 EMA" — draws whatever the selected
        # strategy's own build_indicators() declares (name/count vary).
        self._ema_check = self._add_checkbox(
            layout, "chkChartEma", "Strategy Indicators"
        )
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

        layout.addSpacing(12)

        self._marker_outcome_combo = self._add_enum_combo(
            layout, "cboMarkerOutcomeFilter", _OUTCOME_LABELS
        )
        self._marker_outcome_combo.currentIndexChanged.connect(
            self._emit_marker_filter_changed
        )

        self._marker_side_combo = self._add_enum_combo(
            layout, "cboMarkerSideFilter", _SIDE_LABELS
        )
        self._marker_side_combo.currentIndexChanged.connect(
            self._emit_marker_filter_changed
        )

        self._marker_min_pnl_spin = QtWidgets.QDoubleSpinBox()
        self._marker_min_pnl_spin.setObjectName("spinMarkerMinPnl")
        self._marker_min_pnl_spin.setRange(0.0, _MAX_MIN_PNL_PERCENT)
        self._marker_min_pnl_spin.setSuffix("% min |PnL|")
        self._marker_min_pnl_spin.setSingleStep(0.5)
        self._marker_min_pnl_spin.valueChanged.connect(self._emit_marker_filter_changed)
        layout.addWidget(self._marker_min_pnl_spin)

        layout.addStretch(1)

    @staticmethod
    def _add_checkbox(
        layout: QtWidgets.QHBoxLayout, object_name: str, text: str
    ) -> QtWidgets.QCheckBox:
        check = QtWidgets.QCheckBox(text)
        check.setObjectName(object_name)
        layout.addWidget(check)
        return check

    @staticmethod
    def _add_enum_combo(
        layout: QtWidgets.QHBoxLayout, object_name: str, labels: EnumLabels
    ) -> QtWidgets.QComboBox:
        combo = QtWidgets.QComboBox()
        combo.setObjectName(object_name)
        for member, text in labels.items():
            combo.addItem(text, member)
        layout.addWidget(combo)
        return combo

    def _emit_marker_filter_changed(self, *_args: object) -> None:
        """Bridges `currentIndexChanged(int)`/`valueChanged(float)` into the
        no-payload `sig_marker_filter_changed` — connecting either signal
        straight to `.emit` raises `TypeError` (a real bug this class's own
        test suite caught), since `Signal()` takes zero arguments."""
        self.sig_marker_filter_changed.emit()

    def _on_mode_button_clicked(self, button: QtWidgets.QAbstractButton) -> None:
        for mode, mode_button in self._mode_buttons.items():
            if mode_button is button:
                self.sig_mode_changed.emit(mode.value)
                return

    def set_trade_flags_enabled(self, enabled: bool) -> None:
        """Buy/Sell flags are price-scale markers — meaningless once the
        main plot is showing Equity instead of price (see BackTestView's
        mode-render logic), so Equity-solo mode disables this control rather
        than silently drawing markers nobody asked to see. The 3 marker
        filters (PROP-004) only ever narrow that same marker set, so they
        follow the checkbox's own enabled state."""
        self._trade_flags_check.setEnabled(enabled)
        self._marker_outcome_combo.setEnabled(enabled)
        self._marker_side_combo.setEnabled(enabled)
        self._marker_min_pnl_spin.setEnabled(enabled)

    def is_trade_flags_checked(self) -> bool:
        return self._trade_flags_check.isChecked()

    def outcome_filter(self) -> MarkerOutcomeFilter:
        # `QComboBox.addItem(text, userData=...)` round-trips a `str`-based
        # Enum member through `QVariant` as a plain `str` (its own value),
        # not the enum instance — `currentData() is MarkerOutcomeFilter.X`
        # would silently always be `False` without re-wrapping it here.
        return MarkerOutcomeFilter(self._marker_outcome_combo.currentData())

    def side_filter(self) -> MarkerSideFilter:
        return MarkerSideFilter(self._marker_side_combo.currentData())

    def min_pnl_threshold(self) -> float:
        return self._marker_min_pnl_spin.value()

    def set_ema_enabled(self, enabled: bool) -> None:
        """The strategy indicator overlay is price-scale too — left plotted through an
        Equity-solo switch, it stays on the same main plot as the equity
        curve and drags pyqtgraph's auto-range to the price axis (~tens of
        thousands), squashing the equity curve flat. Same treatment as
        `set_trade_flags_enabled`: disable the control, don't just leave the
        stale lines drawn."""
        self._ema_check.setEnabled(enabled)

    def is_ema_checked(self) -> bool:
        return self._ema_check.isChecked()
