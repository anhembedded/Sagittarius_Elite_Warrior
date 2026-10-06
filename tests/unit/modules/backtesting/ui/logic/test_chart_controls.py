"""PROP-004 — the 3 marker-filter controls `BacktestChartControls` grew
alongside the existing mode switch / overlay toggles it already had."""

from PySide6.QtWidgets import QCheckBox, QRadioButton, QToolBar
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.chart_canvas_view import (
    ChartDisplayMode,
    MarkerOutcomeFilter,
    MarkerSideFilter,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.chart_controls import (
    BacktestChartControls,
)


def test_marker_filters_default_to_all_and_zero_threshold(qapp):
    controls = BacktestChartControls()

    assert controls.outcome_filter() is MarkerOutcomeFilter.ALL
    assert controls.side_filter() is MarkerSideFilter.ALL
    assert controls.min_pnl_threshold() == 0.0


def test_changing_the_outcome_combo_emits_the_filter_changed_signal(qapp):
    controls = BacktestChartControls()
    emitted = []
    controls.sig_marker_filter_changed.connect(lambda: emitted.append(True))

    index = controls._marker_outcome_combo.findData(MarkerOutcomeFilter.WINS_ONLY)
    controls._marker_outcome_combo.setCurrentIndex(index)

    assert controls.outcome_filter() is MarkerOutcomeFilter.WINS_ONLY
    assert emitted


def test_changing_the_side_combo_emits_the_filter_changed_signal(qapp):
    controls = BacktestChartControls()
    emitted = []
    controls.sig_marker_filter_changed.connect(lambda: emitted.append(True))

    index = controls._marker_side_combo.findData(MarkerSideFilter.SHORT_ONLY)
    controls._marker_side_combo.setCurrentIndex(index)

    assert controls.side_filter() is MarkerSideFilter.SHORT_ONLY
    assert emitted


def test_changing_the_min_pnl_spinbox_emits_the_filter_changed_signal(qapp):
    controls = BacktestChartControls()
    emitted = []
    controls.sig_marker_filter_changed.connect(lambda: emitted.append(True))

    controls._marker_min_pnl_spin.setValue(5.0)

    assert controls.min_pnl_threshold() == 5.0
    assert emitted


def test_disabling_trade_flags_also_disables_the_3_marker_filters(qapp):
    controls = BacktestChartControls()

    controls.set_trade_flags_enabled(False)

    assert not controls._marker_outcome_combo.isEnabled()
    assert not controls._marker_side_combo.isEnabled()
    assert not controls._marker_min_pnl_spin.isEnabled()

    controls.set_trade_flags_enabled(True)

    assert controls._marker_outcome_combo.isEnabled()
    assert controls._marker_side_combo.isEnabled()
    assert controls._marker_min_pnl_spin.isEnabled()


# -- BOT-155: a toolbar of actions, so the Backtest mode fits 1024×700 ------------


def test_the_controls_are_a_toolbar_that_can_shrink_below_its_contents(qapp):
    """One row of widgets could not shrink below ~1027 px and held the whole
    window at least 1400 px wide; a toolbar overflows into its extension
    button instead."""
    controls = BacktestChartControls()

    assert isinstance(controls, QToolBar)
    assert controls.minimumSizeHint().width() < controls.sizeHint().width() / 2


def test_the_chart_mode_is_one_exclusive_group_of_checkable_actions(qapp):
    controls = BacktestChartControls()
    modes = controls._mode_actions
    emitted: list[str] = []
    controls.sig_mode_changed.connect(emitted.append)

    assert all(a.isCheckable() for a in modes.values())
    assert modes[ChartDisplayMode.OHLC].isChecked()
    assert modes[ChartDisplayMode.OHLC].actionGroup().isExclusive()

    modes[ChartDisplayMode.EQUITY].trigger()

    assert emitted == [ChartDisplayMode.EQUITY.value]
    assert not modes[ChartDisplayMode.OHLC].isChecked()


def test_each_layer_is_a_checkable_action_on_by_default(qapp):
    controls = BacktestChartControls()
    toggled: list[bool] = []
    controls.sig_volume_toggled.connect(toggled.append)
    layers = (
        controls._ema_action,
        controls._volume_action,
        controls._trade_flags_action,
    )

    assert all(a.isCheckable() and a.isChecked() for a in layers)

    controls._volume_action.trigger()

    assert toggled == [False]
    assert controls.is_trade_flags_checked() and controls.is_ema_checked()


def test_no_entry_is_a_radio_button_or_a_check_box(qapp):
    """State is a checkable action on a toolbar (`ui-presentation-rule.md`
    §6), not a button widget the toolbar check would flag."""
    controls = BacktestChartControls()

    assert controls.findChildren(QRadioButton) == []
    assert controls.findChildren(QCheckBox) == []
