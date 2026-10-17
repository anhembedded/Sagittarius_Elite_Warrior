"""`EPIC-029B`, `EPIC-034H`, `EPIC-029J` J1a, J1b — who else holds the symbol, and is the venue full (ADR D20).

Bots on different symbols of a venue run together; two bots never share a symbol of a venue
(trading's symbol lease is the rule at the exchange, this is the same rule asked before the click,
so it can name the holder). "Active" is every state a new run does not start from
(`RUN_STARTING_STATES`): a STARTING, PAUSED, HALTED, RECOVERING, STOPPING or ERROR bot may still
own orders, a lease or a budget. A venue also holds at most `MAX_ACTIVE_BOTS_PER_VENUE` active
bots, because they spend one account's weight, order rate and margin. A venue with a RECOVERING
bot starts nothing else: opening its session would resume that bot too. A file the store refused
counts as holding every symbol: its state, venue and symbol are unknown, so it is the worst case.
One module, so the Start path and the readiness reader (the store's reading) and the Bots screen
(the list's snapshot) answer the same.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RUN_STARTING_STATES,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.venue_bot_cap import (
    MAX_ACTIVE_BOTS_PER_VENUE,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True, slots=True)
class BotSlot:
    """What a bot takes from a venue: where it trades and whether it may still hold orders."""

    bot_id: str
    venue: TradingVenue
    symbol: str
    state: BotLifecycleState

    @property
    def is_active(self) -> bool:
        return self.state not in RUN_STARTING_STATES


def other_active_bot(
    bot_id: str,
    venue: TradingVenue,
    symbol: str,
    bots: Iterable[BotSlot],
    refused_files: Iterable[str] = (),
) -> str:
    """The id (or the refused file's name) of another active bot on `venue` and `symbol`;
    `""` when none."""
    for slot in bots:
        if (
            slot.bot_id != bot_id
            and slot.venue is venue
            and slot.symbol == symbol
            and slot.is_active
        ):
            return slot.bot_id
    for name in refused_files:
        if not name.startswith(f"{bot_id}."):
            return name
    return ""


def venue_is_full(
    bot_id: str, venue: TradingVenue, bots: Iterable[BotSlot]
) -> tuple[str, ...]:
    """The ids of the other active bots of `venue` when they already number the cap, in the order
    given; `()` when another bot may join them."""
    others = tuple(
        slot.bot_id
        for slot in bots
        if slot.bot_id != bot_id and slot.venue is venue and slot.is_active
    )
    return others if len(others) >= MAX_ACTIVE_BOTS_PER_VENUE else ()


def venue_recovering(
    bot_id: str, venue: TradingVenue, bots: Iterable[BotSlot]
) -> tuple[str, ...]:
    """The ids of the other bots of `venue` that are RECOVERING, in the order given.

    A Start opens the venue's order session, and opening it reconciles every RECOVERING bot of
    the venue and lets it trade (`BotEventRouter.on_switch`; `EPIC-042E`'s latent risk): a bot the
    owner has not resumed would start trading because another one was started. So the Start waits
    until they are resumed or stopped, as J1a's one-bot rule made it wait."""
    return tuple(
        slot.bot_id
        for slot in bots
        if slot.bot_id != bot_id
        and slot.venue is venue
        and slot.state is BotLifecycleState.RECOVERING
    )


@dataclass(frozen=True, slots=True)
class VenueOccupancy:
    """What the other bots leave a bot of `venue` and `symbol`: the symbol's holder, the bots
    that fill the venue and the bots still waiting to recover on it. All are empty when the bot
    may start."""

    symbol_holder: str = ""
    venue_full_of: tuple[str, ...] = ()
    venue_recovering: tuple[str, ...] = ()


def occupancy_of(
    bot_id: str,
    venue: TradingVenue,
    symbol: str,
    bots: Iterable[BotSlot],
    refused_files: Iterable[str] = (),
) -> VenueOccupancy:
    """The one reading the Start path, the readiness reader and the Bots screen share."""
    slots = tuple(bots)
    return VenueOccupancy(
        other_active_bot(bot_id, venue, symbol, slots, refused_files),
        venue_is_full(bot_id, venue, slots),
        venue_recovering(bot_id, venue, slots),
    )
