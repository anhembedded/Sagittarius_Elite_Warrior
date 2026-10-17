"""`EPIC-042C` (ADR 042 D1) - a bot resumed by itself after a transient halt.

The typed fact the `BOT_AUTO_RECOVERED` alert is built on (`EPIC-042D`). It is an event and not a
state entry because the bot enters STARTING for every start and every Resume: only the recovery
run knows this one was automatic, and which attempt of the budget it was.
"""

from __future__ import annotations

from dataclasses import dataclass

from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class BotAutoRecoveredEvent(BaseEvent):
    """
    @brief Published once per automatic recovery, after the new ladder is laid or the attempt
    otherwise left the waiting state for STARTING.

    @details Kind-neutral. Published from the bot's worker thread, so a consumer marshals itself.
    Not `frozen`, for the same `BaseEvent` reason `BotStopGaveUpEvent` documents.
    """

    bot_id: str
    #: The halt reason that recovered (`GridReason.value`).
    reason: str
    #: Which attempt of the rolling budget this was, and how many the budget allows.
    attempt: int
    max_attempts: int
