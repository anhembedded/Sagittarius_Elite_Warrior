"""`BUG-250` — the runs of a venue that may own a position its account holds.

@details A closed order session refuses every position of the account (`SessionReadiness`), and a
host stop that leaves a Futures bot under its protective stop (`EPIC-038M`, O12) leaves the bot's
own position there: the restart's RECOVERING bot can be resumed only through the session. A bot
acting on its own run (its Resume, its Stop) therefore names the venue's runs that may own a
position, and trading excuses a position only when one of those runs' tagged history explains it
(`PositionExplainer`).

The claim names **whose** history to read, never what it says: it carries the owner id, the tag
(the bot's id, `grid_registration`), the symbol and the run start, and no quantity. The bot's file
never supplies a quantity (`IBotStore`): a hand-edited file can name a claim, but only orders
carrying the bot's tag count, and what the history adds up to must equal the account's position. The
file does choose the evidence window (`run_started_at`), as a budget registration's does. Every bot of the venue that has started a run and is not at rest counts
(`RUN_STARTING_STATES` are DRAFT and STOPPED): a RECOVERING, HALTED or PAUSED bot may own a
position, and the session's opening is venue-wide, so the first Resume must have the positions of
the venue's other waiting bots explained too. Excusing a position does not resume its bot: that
still takes its own Resume (decision O2).
"""

from __future__ import annotations

from collections.abc import Iterable

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_budget import (
    bot_owner_id,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RUN_STARTING_STATES,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position_claim import (
    OwnerPositionClaim,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def venue_position_claims(
    venue: TradingVenue, bots: Iterable[Bot]
) -> tuple[OwnerPositionClaim, ...]:
    """The claims of `venue`'s bots that are mid-run, in the order given."""
    return tuple(
        OwnerPositionClaim(
            owner_id=bot_owner_id(bot.bot_id.value),
            tag=bot.bot_id.value,
            symbol=bot.definition.symbol,
            run_started_at=bot.lifecycle.run_started_at,
        )
        for bot in bots
        if bot.definition.venue is venue
        and bot.state not in RUN_STARTING_STATES
        and bot.lifecycle.run_started_at is not None
    )
