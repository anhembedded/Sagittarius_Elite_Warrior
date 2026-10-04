"""`EPIC-029F` — a bot was saved or deleted; the Bots tab reads it again."""

from __future__ import annotations

from dataclasses import dataclass

from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class BotChangedEvent(BaseEvent):
    """
    @brief Published once for every write to the bot store: a definition
    created or edited, a state change, a fill booked by the executor, or a
    delete.

    @details The store is the one place every change to a bot passes through
    (use cases and executors alike), so publishing there covers each writer
    without each remembering to. The event names the bot only; a reader asks
    `GetBotQuery` for what changed. It is published from whichever thread
    wrote, so a screen receives it through a Qt-marshalling feed.

    @par Not `frozen` — the same `BaseEvent` inheritance cost
    `OrderEndedEvent` documents. Treat as read-only by convention.
    """

    bot_id: str
    #: True when the bot's file was deleted.
    removed: bool = False
