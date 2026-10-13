"""`EPIC-039H` — a closed venue refuses every way of creating, moving, starting or resuming a bot.

@details Futures mainnet stays closed to bots until `EPIC-039L` (an exchange-side stop for every
position and the owner's testnet soak, `CLOSED_VENUES`). The picker not listing it is not a gate:
a plan file and `run --start-planned --confirm-venue futures_mainnet`, a command from code or a
bot file already on disk reach the same use cases. So the refusal is one function in the use
cases' own words, called first by each of them, before real money is asked about.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    bot_closed_reason,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def closed_venue_refusal(
    venue: TradingVenue, bot_id: str | None = None
) -> BotCommandResult | None:
    """The refusal for `venue` if it is closed to bots, else `None`."""
    reason = bot_closed_reason(venue)
    if reason is None:
        return None
    return BotCommandResult.refused(BotRefusal.VENUE_NOT_READY, reason, bot_id)
