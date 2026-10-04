"""`EPIC-029G` — the one drawer of a bot's overlay (ADR D16).

@details The planner preview, the backtest result and the running bot each
host a `BotChart`, and every `BotChart` draws through this class, so the
three put the same items on their charts for the same overlay. Lines and
bands go to the chart's `PriceLevelLayer`, fills to its marker layer; each
draw replaces the previous one under the drawer's keys, so drawing an
empty overlay clears them.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.overlay_items import (
    OverlayItems,
    overlay_items,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.price_level_layer import (
    PriceLevelLayer,
)

#: The keys a bot's overlay is drawn under, on the level layer and the
#: marker layer.
OVERLAY_KEY = "bot.overlay"
FILLS_KEY = "bot.fills"


class BotOverlayDrawer:
    """@brief Draws one `BotOverlay` onto one chart."""

    def __init__(self, chart: ChartCard, levels: PriceLevelLayer) -> None:
        self._chart = chart
        self._levels = levels

    def draw(self, overlay: BotOverlay) -> OverlayItems:
        """@brief Replaces what the chart shows of the bot with `overlay`.
        @return The items drawn."""
        items = overlay_items(overlay)
        self._levels.set_levels(OVERLAY_KEY, items.levels)
        self._levels.set_bands(OVERLAY_KEY, items.bands)
        self._chart.set_script_markers(FILLS_KEY, list(items.markers))
        return items
