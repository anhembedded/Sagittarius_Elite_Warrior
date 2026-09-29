"""`EPIC-028B` — one armed strategy per trading venue.

@details A `LiveStrategySession` holds exactly one armed strategy and the
`LiveTradingCoordinator` that sends its orders (`BUG-085`: one engine is fed
one symbol and one interval). With Futures and Spot live at once, each venue
gets its own session, built on first use with that venue's own trading ports,
so a strategy armed on Spot sends its orders to Spot and is refused SHORT by
Spot's rules (`EPIC-027N`), whatever is armed on Futures.

`build` is supplied by the composition root: it knows how to reach a venue's
published ports (`IVenueTradingPorts`, `IVenueContexts`). This class only
keeps one session per venue.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class VenueStrategySessions:
    """The live strategy session of each venue, the same one on every call."""

    def __init__(self, build: Callable[[TradingVenue], LiveStrategySession]) -> None:
        self._build = build
        self._sessions: dict[TradingVenue, LiveStrategySession] = {}
        self._lock = threading.Lock()

    def get(self, venue: TradingVenue) -> LiveStrategySession:
        """@raise VenueNotEnabledError (from `build`) when `venue` is not
        served, before any session exists for it."""
        with self._lock:
            session = self._sessions.get(venue)
            if session is None:
                session = self._build(venue)
                self._sessions[venue] = session
            return session

    def built_for(self, market: MarketType) -> tuple[LiveStrategySession, ...]:
        """The sessions built so far whose venue trades `market` (`EPIC-028C`):
        the ones a candle from that market's stream may feed. A venue never
        asked for has never had a strategy armed, so it has nothing to
        receive a tick."""
        with self._lock:
            return tuple(
                session
                for venue, session in self._sessions.items()
                if venue.market_type is market
            )
