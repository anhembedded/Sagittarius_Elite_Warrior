"""`EPIC-029E` — makes "no other bot is active" and "this one starts" one step (ADR D20).

`StartBotCommandHandler` reads every bot, finds none active, then starts this
one. Without a lock two starts dispatched at once could both pass the check
(the PR #318 review). One instance, shared by every start, holds the check and
the transition together.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager


class BotCommandLock:
    """One lock for the commands that must see every bot at once."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    @contextmanager
    def held(self) -> Iterator[None]:
        with self._lock:
            yield
