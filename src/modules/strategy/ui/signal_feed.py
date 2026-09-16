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

@par This bus carries backtest signals too
`SignalGeneratedEvent` goes out on the same `IEventBus` a *backtest* run's
own `StrategyEngine` publishes on — which is exactly why
`MarketTickEventHandler` refuses to route ORDERS through it (see that
class's docstring: a coordinator subscribed here could fire a real order
from a backtest run). Displaying a line of text is a different matter, but
not a free one: a backtest running while the Trading screen is open would
otherwise scribble its signals into a card that claims to describe live
trading. `TradingPresenter` therefore filters to the armed symbol before
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
