"""`EPIC-029E` — each bot's worker is closed when its executor goes (PR 325 review).

A worker is a thread. Replacing an executor for a new run, or shutting the
module down, closes the old queue: it runs what is queued and stops, so no
thread leaks per restart and no stale task writes an old run's bot over the
new one's file.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_work_queue import (
    IBotWorkQueue,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    grid_world,
)


class _ClosingQueue(IBotWorkQueue):
    def __init__(self) -> None:
        self.closed = False

    def post(self, task: Callable[[], None]) -> None:
        task()

    def close(self) -> None:
        self.closed = True


def _executors() -> tuple[BotExecutors, list[_ClosingQueue], Bot]:
    queues: list[_ClosingQueue] = []

    def queue(_name: str) -> _ClosingQueue:
        queues.append(_ClosingQueue())
        return queues[-1]

    world = grid_world(queues=queue)
    queues.clear()  # the world's own executor is not under test
    return BotExecutors(world.factory), queues, world.store.load(BotId(BOT)).bot


def test_a_fresh_executor_closes_the_one_it_replaces() -> None:
    executors, queues, bot = _executors()
    executors.for_bot(bot)

    executors.fresh(bot)

    assert [queue.closed for queue in queues] == [True, False]


def test_retiring_closes_the_worker_and_forgets_the_executor() -> None:
    executors, queues, bot = _executors()
    executors.for_bot(bot)

    executors.retire(BOT)

    assert queues[0].closed
    assert executors.get(BOT) is None


def test_closing_all_closes_every_worker() -> None:
    executors, queues, bot = _executors()
    executors.for_bot(bot)

    executors.close_all()

    assert all(queue.closed for queue in queues)
    assert executors.all() == ()
