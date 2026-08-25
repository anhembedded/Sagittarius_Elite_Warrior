"""
@brief `EngineEventPublisher` — implements `IEventPublisher` on top of the
engine's `IEventBus`.

@details The whole point of `IEventPublisher` (`EPIC-008F`) is that the
Application layer never names `IEventBus`. This adapter is the single place
that does, and it lives in Infrastructure where depending on the engine is
allowed (`code-rule.md` §5).

`EPIC-008F` suggested `src/infrastructure/events/` for this file. It is here
instead: `engine_adapters/` already holds exactly this kind of object — a thin
wrapper turning an engine service into an Application-layer port
(`live_stream_adapter.py`) — and grouping by *topic* (events) rather than by
*abstraction level* (adapters over the engine) is the split `code-rule.md` §7
rules out.
"""

from Sagittarius_Elite_Warrior.src.application.ports.i_event_publisher import (
    IEventPublisher,
)
from sagittarius_engine.domain.i_domain_event import IDomainEvent
from sagittarius_engine.interfaces.i_event_bus import IEventBus


class EngineEventPublisher(IEventPublisher):
    """
    @brief Publishes domain events through the engine's event bus.
    """

    def __init__(self, event_bus: IEventBus) -> None:
        self._event_bus = event_bus

    def publish(self, event: IDomainEvent) -> None:
        """
        @brief Emits `event` on the bus.

        @details Passes the event object itself rather than a
        `(name, payload)` pair: the bus derives the key from `event_name`, so
        a subscriber addressing the event by its pinned wire string and a
        publisher sending the object cannot drift apart.
        """
        self._event_bus.emit(event)
