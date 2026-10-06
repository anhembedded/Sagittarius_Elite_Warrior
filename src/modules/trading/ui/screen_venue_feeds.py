"""`EPIC-028C` — the order, equity and signal feeds of a screen that shows
one venue.

@details Futures and Spot publish onto one event bus. A desk (`EPIC-028K`/`L`)
builds its `OrderFeed`, `EquityFeed` and `SignalFeed` here for its own venue
(`build_for`), so a Spot fill never reaches a Futures table. The signal feed
joined the bundle in `EPIC-028K`: a strategy's signal names its venue too.
The primary venue's bundle (`build`) and its chart market went with the Dev
Board, its only reader (`EPIC-033P`).
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.modules.trading.ui.equity_feed import EquityFeed
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_feed import OrderFeed
from Sagittarius_Elite_Warrior.src.modules.trading.ui.signal_feed import SignalFeed
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus


@dataclass(frozen=True)
class ScreenVenueFeeds:
    """One screen's feeds, all for the same venue."""

    orders: OrderFeed
    equity: EquityFeed
    signals: SignalFeed


def build_for(
    event_bus: IEventBus, venue: TradingVenue, parent: QObject
) -> ScreenVenueFeeds:
    """The feeds of a screen that shows `venue` (a desk)."""
    return ScreenVenueFeeds(
        orders=OrderFeed(event_bus, venue, parent=parent),
        equity=EquityFeed(event_bus, venue, parent=parent),
        signals=SignalFeed(event_bus, venue, parent=parent),
    )
