"""`EPIC-029B`, `EPIC-034H` — which other bot, if any, still holds the exchange (ADR D20).

During the fast track one bot at a time may hold the exchange. "Active" is
every state a new run does not start from (`RUN_STARTING_STATES`): a STARTING,
PAUSED, HALTED, RECOVERING, STOPPING or ERROR bot may still own orders, a lease
or a budget. A file the store refused counts as active too: its state is
unknown, so it is the worst case. One function, so the Start path (the store's
reading) and the Bots screen (the list's snapshot) answer the same.
"""

from __future__ import annotations

from collections.abc import Iterable

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RUN_STARTING_STATES,
    BotLifecycleState,
)


def other_active_bot(
    bot_id: str,
    bots: Iterable[tuple[str, BotLifecycleState]],
    refused_files: Iterable[str] = (),
) -> str:
    """The id (or the refused file's name) of another active bot; `""` when none."""
    for other_id, state in bots:
        if other_id != bot_id and state not in RUN_STARTING_STATES:
            return other_id
    for name in refused_files:
        if not name.startswith(f"{bot_id}."):
            return name
    return ""
