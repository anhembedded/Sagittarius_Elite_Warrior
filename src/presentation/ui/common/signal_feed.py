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

`EPIC-025` PR 4.3m: its only tie to `strategy` is the published
`SignalGeneratedEvent`, so this stays presentation's own file rather than
an import of `modules.strategy.ui.signal_feed` (`architecture-rule.md`
§3, §6: a subscriber is owned by what it drives). Trading and Dev Board
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
showing anything — the filter belongs at the consumer, since the event
itself cannot know which engine produced it.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.events.signal_generated_event import (
    SignalGeneratedEvent,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.base_feed import BaseFeed


class SignalFeed(BaseFeed):
    """@brief Forwards `SignalGeneratedEvent`, already marshaled onto the
    main Qt thread."""

    #: Carries a `SignalGeneratedEvent`.
    signalGenerated = Signal(object)

    def _subscribe(self) -> None:
        self._events.on(SignalGeneratedEvent, self._on_signal_generated)

    def _on_signal_generated(self, event: Any) -> None:
        self.signalGenerated.emit(event)
