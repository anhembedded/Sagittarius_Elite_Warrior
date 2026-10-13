"""What the host does to the bots when it is told to stop (`EPIC-038D`, decision O1).

A policy is a strategy: `LeaveOrdersResting` (the default) closes nothing on the
exchange and says what it leaves; `StopBotsFirst` (`--on-stop stop-bots`) stops
each bot that is not at rest, for maintenance. The host owns the clock: it runs
the policy on a worker thread, waits `--stop-timeout`, and reads the `StopLedger`
to say what did not finish. A policy therefore writes down what it is doing as it
does it, and watches `give_up` so it stops asking the exchange for more once the
host has stopped waiting.

@par Extension cases
  · a third policy (decision O1's option C, a policy per bot kind) - one
    `IShutdownPolicy` and one entry in the table that maps `--on-stop`'s words to
    policies; `RunHost` does not change.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BotLeftBehind:
    """A bot the host stopped waiting for, and what it was doing when it did."""

    bot_id: str
    #: The bot's state when the policy last looked (`STOPPING`, `RUNNING`, ...).
    state: str
    #: How many orders the bot had resting on the exchange; `None` when unknown.
    resting_orders: int | None
    #: Why, in a sentence, when the policy knows (`"the stop was refused: ..."`).
    note: str = ""


class StopLedger:
    """What a policy has done, written by it and read by the host.

    Thread-safe: the policy writes from its worker thread while the host reads
    from the main thread when it gives up.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._open: dict[str, BotLeftBehind] = {}
        self._closed: list[str] = []

    def begin(
        self, bot_id: str, state: str, resting_orders: int | None, note: str = ""
    ) -> None:
        """The policy has taken `bot_id` on; until `finish`, it counts as left."""
        with self._lock:
            self._open[bot_id] = BotLeftBehind(bot_id, state, resting_orders, note)

    def update(self, bot_id: str, state: str, note: str = "") -> None:
        """What the policy last saw of a bot it has begun."""
        with self._lock:
            held = self._open.get(bot_id)
            if held is not None:
                self._open[bot_id] = BotLeftBehind(
                    bot_id, state, held.resting_orders, note or held.note
                )

    def finish(self, bot_id: str) -> None:
        with self._lock:
            if self._open.pop(bot_id, None) is not None:
                self._closed.append(bot_id)

    def left(self) -> tuple[BotLeftBehind, ...]:
        """The bots begun and not finished, in the order they were begun."""
        with self._lock:
            return tuple(self._open.values())

    def finished(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._closed)


class IShutdownPolicy(ABC):
    #: The word `--on-stop` takes, and the word the logs use.
    name: str

    @abstractmethod
    def apply(self, ledger: StopLedger, give_up: threading.Event) -> None:
        """Do the policy's work, recording each bot in `ledger`.

        Returns when the work is done or when `give_up` is set. It may raise: the
        host logs the failure at ERROR and carries on to close the workers.
        """
