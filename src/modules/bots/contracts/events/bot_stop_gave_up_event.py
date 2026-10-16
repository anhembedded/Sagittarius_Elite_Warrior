"""`EPIC-036G` (decision D4) — a bot's stop gave up after its automatic retries.

The typed fact the `STOP_FAILED` alert is built on. Until it existed the give-up
was text appended to the bot's reason and an ERROR log line
(`grid_stop_retry.py`), and a reader would have had to match that text: a
wording change would have silenced the alert with nothing failing.
"""

from __future__ import annotations

from dataclasses import dataclass

from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class BotStopGaveUpEvent(BaseEvent):
    """
    @brief Published once per round of a stop when its automatic retries are used
    up and the bot is still STOPPING: orders the bot placed may still be open.

    @details Kind-neutral: any bot kind whose stop retries publishes it with the
    number of retries it ran, so a consumer needs no change for a new kind.
    Asking Stop again starts a new round, and a round that gives up again
    publishes again. Published from the bot's worker thread, so a consumer
    marshals itself.

    @par Not `frozen` — the same `BaseEvent` inheritance cost `BotChangedEvent`
    documents. Treat as read-only by convention.
    """

    bot_id: str
    #: How many automatic retries ran before the stop gave up.
    retries: int
