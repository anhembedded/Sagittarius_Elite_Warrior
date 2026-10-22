"""`EPIC-046B` - the trigger line shares its style with no other line of a Grid's chart.

The owner reads the entry limit apart from the range, the levels and the exits (`BUG-207` taught
that a shared style is read as the other line's meaning).
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import (
    OverlayLine,
    OverlayRole,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.overlay_items import (
    overlay_items,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.chart.bot_chart_fixtures import (
    sample_overlay,
)


def test_neither_the_trigger_lines_colour_nor_its_dash_is_any_other_lines() -> None:
    trigger = OverlayLine(Decimal(64000), OverlayRole.TRIGGER, "Trigger ≤ 64000")
    overlay = replace(sample_overlay(), lines=(*sample_overlay().lines, trigger))
    levels = overlay_items(overlay).levels
    [drawn] = [level for level in levels if level.label == trigger.label]

    others = [level for level in levels if level.label != trigger.label]
    assert others, "the sample draws levels, a range, exits and an average"
    assert all(level.color != drawn.color for level in others)
    assert all(level.style != drawn.style for level in others)
