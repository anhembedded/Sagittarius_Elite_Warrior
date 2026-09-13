"""An `IEventPublisher` that keeps every event it was given."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.application.ports.i_event_publisher import (
    IEventPublisher,
)
from sagittarius_engine.domain.i_domain_event import IDomainEvent


class RecordingEventPublisher(IEventPublisher):
    def __init__(self) -> None:
        self.events: list[IDomainEvent] = []

    def publish(self, event: IDomainEvent) -> None:
        self.events.append(event)
