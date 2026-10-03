"""An `IEventPublisher` that keeps every event it was given, for the
trading module's unit tests. Derived from the port (`testing-rule.md` §2)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from sagittarius_engine.domain.i_domain_event import IDomainEvent


class RecordingPublisher(IEventPublisher):
    def __init__(self) -> None:
        self.events: list[IDomainEvent] = []

    def publish(self, event: IDomainEvent) -> None:
        self.events.append(event)

    def of_type[EventT](self, event_type: type[EventT]) -> list[EventT]:
        return [event for event in self.events if isinstance(event, event_type)]
