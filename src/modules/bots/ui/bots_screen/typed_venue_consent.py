"""`EPIC-047E` (AC4, charter G3) — the real-money question of the VPS tab: the venue is typed, every time.

@details The Bots tab asks once per mainnet venue per session and remembers the answer. A command to the VPS is the same act
on a host that cannot ask, so the tab asks as the command line does (`--confirm-venue`): the person types the venue's own
identifier, for each Start, Resume, Confirm resume and Stop that reopens a session, and nothing is remembered. The typed
word travels to the host as `confirmed_venue` and the host's gate judges it (decision O8): this class only refuses to build
the command when the person did not type it. Stop is the one command that is still sent without it: a Stop only reduces
exposure, so declining the question stops the bot and opens no order session (`bot_commands.py`, `BUG-274`). A testnet venue is never asked.

@par Extension cases
  · another way to ask (a hardware key, a second person) - another `ask`; the class and the host's gate do not change.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_real_money_consent import (
    IRealMoneyConsent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.RealMoney")

#: Asks the person to type the venue; the text typed, or `None` when they cancelled.
type AskTyped = Callable[[TradingVenue, str], str | None]


class TypedVenueConsent(IRealMoneyConsent):
    def __init__(self, ask: AskTyped) -> None:
        self._ask = ask

    def confirmed(self, venue: TradingVenue, action: str) -> bool:
        if not venue.is_mainnet:
            return True
        typed = self._ask(venue, action)
        agreed = typed is not None and typed.strip() == venue.confirmation_word
        logger.info(
            "Real money on %s for %r through the VPS: %s [real-money]",
            venue.display_name,
            action,
            "typed" if agreed else "not confirmed",
        )
        return agreed
