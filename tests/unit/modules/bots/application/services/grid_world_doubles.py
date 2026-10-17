"""The small doubles `grid_world` builds a Grid executor with: an inline queue, a counting pacer, a recording bus."""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_work_queue import (
    IBotWorkQueue,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_pacer import (
    IOrderPacer,
)
from sagittarius_engine.domain.i_domain_event import IDomainEvent


class InlineWorkQueue(IBotWorkQueue):
    """Runs each task as it is posted, on the poster's thread."""

    def post(self, task: Callable[[], None]) -> None:
        task()

    def close(self) -> None:
        return None


class CountingPacer(IOrderPacer):
    def __init__(self) -> None:
        self.turns = 0

    def wait_turn(self) -> None:
        self.turns += 1


class RecordingPublisher(IEventPublisher):
    """The bus, as far as a bot is concerned: it keeps what it was handed."""

    def __init__(self) -> None:
        self.events: list[IDomainEvent] = []

    def publish(self, event: IDomainEvent) -> None:
        self.events.append(event)
