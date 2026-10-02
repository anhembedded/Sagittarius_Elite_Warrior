"""The one place `trading`'s screens reach `market_data`'s `MarketTickFeed`.

@details `MarketTickFeed` is `market_data`'s Feed for its own event
(`BOT-019`), and a screen that charts candles listens through it rather than
through a copy of its own. Before `EPIC-028K` the Trading screen and the Dev
Board each imported it, two lines in `allowlist_module_boundaries.txt`; the
desks would have made a third. Every trading screen now builds its Feed here,
so the crossing is one line and stays one however many screens chart.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.market_tick_feed import (
    MarketTickFeed,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus


def market_tick_feed(
    event_bus: IEventBus, market: Callable[[], MarketType], parent: QObject
) -> MarketTickFeed:
    """A Feed forwarding, on the Qt thread, the ticks of the market `market`
    names at each tick (`MarketTickFeed`)."""
    return MarketTickFeed(event_bus, market, parent=parent)
