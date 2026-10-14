"""`BOT-176` — "the stored bots as a plan document"."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExportBotPlanQuery:
    """Which bots, and whether the plan wants them all stopped.

    `bot_ids` empty means every bot. `all_stopped` writes every entry's
    `desired_state` as `stopped` whatever the bot is doing or the record says, so a
    plan taken from a running desktop starts nothing on a server that runs
    `--start-planned`.
    """

    bot_ids: tuple[str, ...] = ()
    all_stopped: bool = False
