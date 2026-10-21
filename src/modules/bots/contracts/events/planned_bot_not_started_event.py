"""`EPIC-045F` (ADR 045 D7) - the host did not start a bot its applied plan wants running.

The typed fact the `PLANNED_BOT_NOT_STARTED` alert is built on. `run --start-planned` used to refuse
the whole run (exit 2, which systemd does not restart) when one planned bot was on a mainnet venue the
operator had not typed; every other bot was left unattended. It now skips that bot, says so, and runs
the rest, so the skipped bot is the thing a person must hear about.
"""

from __future__ import annotations

from dataclasses import dataclass

from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class PlannedBotNotStartedEvent(BaseEvent):
    """
    @brief Published once per skipped bot, by the host's `start-planned` step at start.

    @details Published from the host's start-up thread, before any signal is served. `venue` is the
    `TradingVenue` value, which is also what `bot start <id> --confirm-venue` takes. Not `frozen`,
    for the same `BaseEvent` reason `BotStopGaveUpEvent` documents.
    """

    bot_id: str
    venue: str
    #: Why it was skipped, one sentence for a person (it names the command that starts the bot).
    reason: str
