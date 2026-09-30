"""`EPIC-028C` — the order and equity feeds of a screen that shows one venue,
and the market its chart streams.

@details Futures and Spot publish onto one event bus. A screen builds its
`OrderFeed` and `EquityFeed` here, for the venue it shows, so neither the Dev
Board nor the Trading screen has to know how that venue is chosen, and a Spot
fill never reaches a Futures table.

Today every screen shows the primary venue (`TradingVenue`, the first enabled
one). When the two desks exist (`EPIC-028K`/`L`), each desk passes its own
venue instead of resolving it here; that is this one function changing.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.equity_feed import EquityFeed
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_feed import OrderFeed
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_event_bus import IEventBus


@dataclass(frozen=True)
class ScreenVenueFeeds:
    """One screen's feeds, both for the same venue."""

    orders: OrderFeed
    equity: EquityFeed


def build(
    event_bus: IEventBus, container: IContainer, parent: QObject
) -> ScreenVenueFeeds:
    venue = container.resolve(TradingVenue)
    return ScreenVenueFeeds(
        orders=OrderFeed(event_bus, venue, parent=parent),
        equity=EquityFeed(event_bus, venue, parent=parent),
    )


def chart_market(container: IContainer) -> MarketType:
    """The market a venue screen's chart syncs, reads and streams: its
    venue's, so a strategy armed on Futures is fed Futures candles. Spot while
    trading is off (`DISABLED` has no market), which is what every screen
    charted before a venue could be chosen (`EPIC-027A`)."""
    return container.resolve(TradingVenue).market_type or MarketType.SPOT
