"""PROP-004 — the 3 marker-filter controls `BacktestChartControls` grew
alongside the existing mode switch / overlay toggles it already had."""

from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.chart_canvas_view import (
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
