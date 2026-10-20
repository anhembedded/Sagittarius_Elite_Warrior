"""`BUG-243`: the drawdown chart and the report-comparison chart draw their time axis in the
display time zone the Backtest screen follows, not in the machine's clock.

A plain `pg.DateAxisItem` labels in the machine's local time. The zone is a real IANA zone
set on the production view model, and two zones are tried so that the runner's own clock
can coincide with at most one of them."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_modals import (
    ReportComparisonDialog,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_panels import (
    build_panels,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.tests.chart_axis_labels import drawn_labels, utc_range

#: Six hours of 10 January, picked so that neither zone's local midnight falls inside (pyqtgraph
#: writes the date there, not the hour): Ho Chi Minh (UTC+7) reads 09:00..15:00 for 02:00Z and
#: New York (UTC-5) reads 05:00..11:00 for 10:00Z. A tick at the machine's or the other zone's
#: hour is a wrong zone.
_ZONES = [
    pytest.param(
        "Asia/Ho_Chi_Minh",
        utc_range(10, 2, 6),
        {"10:00", "12:00"},
        {"03:00", "05:00"},
        id="east",
    ),
    pytest.param(
        "America/New_York",
        utc_range(10, 10, 6),
        {"06:00", "08:00"},
        {"12:00", "14:00"},
        id="west",
    ),
]


@pytest.mark.parametrize(("zone", "window", "expected", "absent"), _ZONES)
def test_the_drawdown_chart_follows_the_screens_display_zone(
    qapp: object,
    zone: str,
    window: tuple[float, float],
    expected: set[str],
    absent: set[str],
) -> None:
    view_model = BackTestViewModel()
    panels = build_panels(view_model)
    view_model.time_range.set_display_timezone(zone)

    labels = set(drawn_labels(panels.drawdown._plot_widget, window))

    assert expected <= labels
    assert not absent & labels


@pytest.mark.parametrize(("zone", "window", "expected", "absent"), _ZONES)
def test_the_comparison_chart_follows_the_screens_display_zone(
    qapp: object,
    zone: str,
    window: tuple[float, float],
    expected: set[str],
    absent: set[str],
) -> None:
    view_model = BackTestViewModel()
    dialog = ReportComparisonDialog(view_model)
    view_model.time_range.set_display_timezone(zone)

    labels = set(drawn_labels(dialog._chart._plot_widget, window))

    assert expected <= labels
    assert not absent & labels


def test_a_comparison_dialog_opened_after_the_choice_opens_in_the_chosen_zone(
    qapp: object,
) -> None:
    view_model = BackTestViewModel()
    view_model.time_range.set_display_timezone("Asia/Ho_Chi_Minh")

    dialog = ReportComparisonDialog(view_model)

    assert dialog._chart._plot_widget.getPlotItem().getAxis("bottom").display_zone == (
        "Asia/Ho_Chi_Minh"
    )
