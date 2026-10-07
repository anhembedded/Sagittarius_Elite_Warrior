"""`BUG-177`: a chart's price tags and axis labels are whole inside what the
person sees, at every width.

The owner's Trade mode (Windows, 2560x1440) showed the last-price tag as
"2,56" and the left axis as "750", "700". The tag is a pyqtgraph
`InfLineLabel`, which centres a horizontal line's label on `position`; at the
right edge (`1.0`) half of the tag stood outside the plot's view box, which
clips its children, so the tag was cut at any width.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.price_level_layer import (
    LineStyle,
    PriceLevel,
    PriceLevelLayer,
)
from Sagittarius_Elite_Warrior.tests.unit.support.charting.chart_geometry import (
    axis_problems,
    tag_problems,
)

_BASE = 1_786_772_340.0
_WIDTHS = (446, 700, 1024, 1920)


def _card(qapp, width: int) -> ChartCard:
    card = ChartCard("ETHUSDT")
    card.resize(width, 500)
    card.show()
    card.render_historical_data(
        [
            (_BASE + i * 60.0, 2700.0 + i, 2710.0 + i, 2690.0 + i, 2705.0 + i)
            for i in range(300)
        ]
    )
    qapp.processEvents()
    return card


@pytest.mark.parametrize("width", _WIDTHS)
def test_the_last_price_tag_is_whole_inside_the_plot(qapp, width: int) -> None:
    card = _card(qapp, width)
    card.price_line.update_price(2800.43, is_bullish=False)
    qapp.processEvents()
    assert tag_problems(card) == []


@pytest.mark.parametrize("width", _WIDTHS)
def test_a_price_level_tag_is_whole_inside_the_plot(qapp, width: int) -> None:
    card = _card(qapp, width)
    layer = PriceLevelLayer(card.plot_layout.main_plot)
    layer.set_levels(
        "grid",
        [PriceLevel(2800.0, "#26a69a", LineStyle.DASH, label="Take profit 2,800.00")],
    )
    qapp.processEvents()
    assert tag_problems(card) == []


@pytest.mark.parametrize("width", _WIDTHS)
def test_both_axes_are_whole_inside_the_viewport(qapp, width: int) -> None:
    card = _card(qapp, width)
    card.price_line.update_price(2800.43, is_bullish=False)
    qapp.processEvents()
    assert axis_problems(card) == []
