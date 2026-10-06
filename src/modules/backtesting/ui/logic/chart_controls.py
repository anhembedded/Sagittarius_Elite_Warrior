from PySide6 import QtCore, QtWidgets
from PySide6.QtGui import QAction, QActionGroup
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
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

#: The keys of `display_actions()` for the three layers; the chart modes are
#: keyed by their `ChartDisplayMode` value.
LAYER_INDICATORS = "indicators"
LAYER_VOLUME = "volume"
LAYER_TRADE_FLAGS = "trade_flags"


class BacktestChartControls(QtWidgets.QToolBar):
    """
    @brief Chart-area toolbar for the Backtest Screen: the 3-mode switch plus
    overlay toggles (BOT-056 §2.1/§2.2) and the marker filters (PROP-004).

    @details A stock `QToolBar` above the chart since `BOT-155`. It was a row
    of widgets (`EPIC-033L`) about 1027 px wide that could not shrink, so it
    held the whole window at least 1400 px wide and the mode did not fit
    1024×700 (the conformance suite's `fits_the_window`). A toolbar overflows
    into its extension button instead (Qt `QToolBar`, MS `cmd-toolbars`).

    State is a checkable action (`ui-presentation-rule.md` §6): the chart
    mode is an exclusive `QActionGroup`, each layer a checkable action. The
    two filters and the threshold are widgets the toolbar wraps in a
    `QWidgetAction` each. This is purely "how do I look at data BackTestView
    already has", with no config to validate or dispatch, so it needs no
    ViewModel/Presenter round-trip. Dumb component, the same rule
    `ChartToolbar` itself documents: emits signals, decides nothing.
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
        super().__init__("Chart display", parent)
        self.setObjectName("backtestChartControls")

        # One chart mode at a time is a state: checkable actions in one
        # exclusive group (`ui-presentation-rule.md` §6).
        self._mode_actions: dict[ChartDisplayMode, QAction] = {}
        self._mode_group = QActionGroup(self)
        self._mode_group.setExclusive(True)
        for mode in ChartDisplayMode:
            action = self._add_checkable(
                f"actChartMode_{mode.value}", _MODE_LABELS[mode]
            )
            self._mode_group.addAction(action)
            self._mode_actions[mode] = action
        self._mode_actions[ChartDisplayMode.OHLC].setChecked(True)
        self._mode_group.triggered.connect(self._on_mode_triggered)

        self.addSeparator()

        # BOT-060: no longer a fixed "4 EMA" — draws whatever the selected
        # strategy's own build_indicators() declares (name/count vary).
        self._ema_action = self._add_layer("actChartEma", "Strategy Indicators")
        self._ema_action.toggled.connect(self.sig_ema_toggled.emit)
        self._volume_action = self._add_layer("actChartVolume", "Volume")
        self._volume_action.toggled.connect(self.sig_volume_toggled.emit)
        self._trade_flags_action = self._add_layer(
            "actChartTradeFlags", "Buy/Sell Flags"
        )
        self._trade_flags_action.toggled.connect(self.sig_trade_flags_toggled.emit)

        self.addSeparator()

        self._marker_outcome_combo = self._add_enum_combo(
            "cboMarkerOutcomeFilter", _OUTCOME_LABELS
        )
        self._marker_outcome_combo.currentIndexChanged.connect(
            self._emit_marker_filter_changed
        )

        self._marker_side_combo = self._add_enum_combo(
            "cboMarkerSideFilter", _SIDE_LABELS
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
        self.addWidget(self._marker_min_pnl_spin)

    def display_actions(self) -> dict[str, QAction]:
        """The chart mode's and the layers' actions, by key, for View →
        Chart to drive and follow (`BOT-155`)."""
        actions = {mode.value: action for mode, action in self._mode_actions.items()}
        actions[LAYER_INDICATORS] = self._ema_action
        actions[LAYER_VOLUME] = self._volume_action
        actions[LAYER_TRADE_FLAGS] = self._trade_flags_action
        return actions

    def show_sides_for(self, market: MarketType) -> None:
        """EPIC-027D — a Spot screen offers no "Short Only" marker filter:
        Spot is long-only (ADR D3). A selected one falls back to "All" first,
        which re-emits the filter so the chart redraws its markers."""
        combo = self._marker_side_combo
        index = combo.findData(MarkerSideFilter.SHORT_ONLY)
        if market is MarketType.SPOT and index >= 0:
            if combo.currentIndex() == index:
                combo.setCurrentIndex(combo.findData(MarkerSideFilter.ALL))
            combo.removeItem(index)
        elif market is not MarketType.SPOT and index < 0:
            short_only = MarkerSideFilter.SHORT_ONLY
            combo.addItem(_SIDE_LABELS[short_only], short_only)

    def _add_checkable(self, object_name: str, text: str) -> QAction:
        action = QAction(text, self)
        self.addAction(action)
        action.setObjectName(object_name)
        action.setCheckable(True)
        return action

    def _add_layer(self, object_name: str, text: str) -> QAction:
        """A layer of the chart, drawn until unchecked."""
        action = self._add_checkable(object_name, text)
        action.setChecked(True)
        return action

    def _add_enum_combo(
        self, object_name: str, labels: EnumLabels
    ) -> QtWidgets.QComboBox:
        combo = QtWidgets.QComboBox()
        combo.setObjectName(object_name)
        for member, text in labels.items():
            combo.addItem(text, member)
        self.addWidget(combo)
        return combo

    def _emit_marker_filter_changed(self, *_args: object) -> None:
        """Bridges `currentIndexChanged(int)`/`valueChanged(float)` into the
        no-payload `sig_marker_filter_changed` — connecting either signal
        straight to `.emit` raises `TypeError` (a real bug this class's own
        test suite caught), since `Signal()` takes zero arguments."""
        self.sig_marker_filter_changed.emit()

    def _on_mode_triggered(self, action: QAction) -> None:
        for mode, mode_action in self._mode_actions.items():
            if mode_action is action:
                self.sig_mode_changed.emit(mode.value)
                return

    def set_trade_flags_enabled(self, enabled: bool) -> None:
        """Buy/Sell flags are price-scale markers — meaningless once the
        main plot is showing Equity instead of price (see BackTestView's
        mode-render logic), so Equity-solo mode disables this control rather
        than silently drawing markers nobody asked to see. The 3 marker
        filters (PROP-004) only ever narrow that same marker set, so they
        follow the checkbox's own enabled state."""
        self._trade_flags_action.setEnabled(enabled)
        self._marker_outcome_combo.setEnabled(enabled)
        self._marker_side_combo.setEnabled(enabled)
        self._marker_min_pnl_spin.setEnabled(enabled)

    def is_trade_flags_checked(self) -> bool:
        return self._trade_flags_action.isChecked()

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
        self._ema_action.setEnabled(enabled)

    def is_ema_checked(self) -> bool:
        return self._ema_action.isChecked()
