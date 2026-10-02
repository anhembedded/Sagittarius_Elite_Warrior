"""
@brief `SignalFeed` — `SignalGeneratedEvent`, one place hears it
(`EPIC-022E`).

@details `StrategyEngine` has published this event since `BOT-020`, and
until now nothing in the UI listened. That left a real gap the user hit:
when no order appears, there is no way to tell "the strategy produced no
signal" from "it produced one and something refused it". `BUG-084` closed
half of that by surfacing the refusals (`LiveOrderBlockedEvent` reaching
the Trading log); this Feed closes the other half by surfacing the
signals themselves.

`EPIC-025` PR 4.3m: its only tie to `strategy` was the published
`SignalGeneratedEvent`, so this stayed presentation's own file rather than
an import of `modules.strategy.ui.signal_feed` (`architecture-rule.md`
§3, §6: a subscriber is owned by what it drives). **PR 4.4c (§8) relocates
that event's own home to `modules/trading/contracts/events/`** — the
strategy-side publisher (`StrategyEngine`) keeps writing it, but the type
itself is now trading's, so this file (bound for `modules/trading/ui/`
alongside the screens once they move) never has to import
`modules.strategy.contracts` for it either. Trading and Dev Board
both want it — that is `architecture-rule.md` §6's "reasonable, not
absurd" case for one shared Feed rather than a private signal per screen,
and `tests/unit/architecture/test_presenter_duplication_only_shrinks.py`
is the ratchet that turns "identical copy in each screen" from a shrug
into a measured regression: two copies of this class briefly existed at
`screens/trading/signal_feed.py` and `screens/dashboard/signal_feed.py`
before landing here, which is where the class lived before `EPIC-025` PR
2.1e ever moved it into `modules/strategy/ui/`.

@par This bus carries backtest signals too
`SignalGeneratedEvent` goes out on the same `IEventBus` a *backtest* run's
own `StrategyEngine` publishes on — which is exactly why
`MarketTickEventHandler` refuses to route ORDERS through it (see that
class's docstring: a coordinator subscribed here could fire a real order
from a backtest run). Displaying a line of text is a different matter, but
not a free one: a backtest running while a live screen is open would
otherwise scribble its signals into a card that claims to describe live
trading. Each Presenter therefore filters to its own armed symbol before
showing anything.

`EPIC-028K` — the event now names the venue whose live strategy produced it
(`None` for a backtest), and a Feed forwards only its own venue's, the same
way `OrderFeed` filters: two desks share one bus, and a Spot signal must not
reach the Futures desk's card. A backtest's signal (`venue=None`) reaches no
Feed at all.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.signal_generated_event import (
    SignalGeneratedEvent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.base_feed import BaseFeed
from sagittarius_engine.interfaces.i_event_bus import IEventBus


class SignalFeed(BaseFeed):
    """@brief Forwards `SignalGeneratedEvent`, already marshaled onto the
    main Qt thread."""

    #: Carries a `SignalGeneratedEvent` of this Feed's venue.
    signalGenerated = Signal(object)

    def __init__(
        self,
        event_bus: IEventBus,
        venue: TradingVenue,
        parent: QObject | None = None,
    ) -> None:
        # Set before `super().__init__`: `BaseFeed.__init__` subscribes.
        self._venue = venue
        super().__init__(event_bus, parent)

    def _subscribe(self) -> None:
        self._events.on(SignalGeneratedEvent, self._on_signal_generated)

    def _on_signal_generated(self, event: Any) -> None:
        if event.venue is self._venue:
            self.signalGenerated.emit(event)
