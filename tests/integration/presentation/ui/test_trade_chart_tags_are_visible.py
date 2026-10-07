"""`BUG-177`: in the real Trade mode, at each conformance window size, the
desk chart's price tag and axis labels are whole inside the chart's viewport.

The owner saw the last-price tag as "2,56" and the left axis as "750" on a
2560x1440 window. The unit test (`test_chart_tags_stay_visible.py`) proves the
chart alone; this one proves it where the order-entry dock sits beside it, for
each venue's chart.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_screen import (
    TRADE_ROUTE,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.test_workbench_conformance import (
    WINDOW_SIZES,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.trade_mode_boot import (
    FUTURES,
    SPOT,
    Boot,
    choose,
    trade_mode_running,
)
from Sagittarius_Elite_Warrior.tests.unit.support.charting.chart_geometry import (
    axis_problems,
    tag_problems,
)

_BASE = 1_786_772_340.0


@pytest.fixture
def trade_boot(request: pytest.FixtureRequest) -> Boot:
    return Boot.from_request(request)


def _settle() -> None:
    for _ in range(3):
        QApplication.processEvents()


@pytest.mark.parametrize(
    "size", [QSize(*s) for s in WINDOW_SIZES], ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_a_desks_price_tag_and_axes_are_whole(trade_boot: Boot, size: QSize) -> None:
    with trade_mode_running(trade_boot) as desk:
        desk.window.resize(size)
        _settle()
        for venue in (SPOT, FUTURES):
            choose(desk.window, venue)
            _settle()
            chart = desk.window.hosts[TRADE_ROUTE].view.venue_page(venue).chart
            chart.render_historical_data(
                [
                    (_BASE + i * 60.0, 2700.0 + i, 2710.0 + i, 2690.0 + i, 2705.0 + i)
                    for i in range(300)
                ]
            )
            chart.price_line.update_price(2800.43, is_bullish=False)
            _settle()
            assert tag_problems(chart) == [], venue
            assert axis_problems(chart) == [], venue
