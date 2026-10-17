"""`EPIC-029B`, `EPIC-034H`, `EPIC-029J` J1a — which other bot, if any, still holds the venue (ADR D20).

One bot at a time may hold a venue (a venue is Spot or Futures, mainnet or
testnet: `TradingVenue`); bots on different venues run together. "Active" is
every state a new run does not start from (`RUN_STARTING_STATES`): a STARTING,
PAUSED, HALTED, RECOVERING, STOPPING or ERROR bot may still own orders, a lease
or a budget. A file the store refused counts as active on every venue: its
state and venue are unknown, so it is the worst case. One function, so the
Start path and the readiness reader (the store's reading) and the Bots screen
(the list's snapshot) answer the same.
"""

from __future__ import annotations

from collections.abc import Iterable

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RUN_STARTING_STATES,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def other_active_bot(
    bot_id: str,
    venue: TradingVenue,
    bots: Iterable[tuple[str, TradingVenue, BotLifecycleState]],
    refused_files: Iterable[str] = (),
) -> str:
    """The id (or the refused file's name) of another active bot on `venue`; `""` when none."""
    for other_id, other_venue, state in bots:
        if (
            other_id != bot_id
            and other_venue is venue
            and state not in RUN_STARTING_STATES
        ):
            return other_id
    for name in refused_files:
        if not name.startswith(f"{bot_id}."):
            return name
    return ""
