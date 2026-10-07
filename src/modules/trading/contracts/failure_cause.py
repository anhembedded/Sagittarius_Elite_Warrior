"""`BOT-169` — the key one failure of one venue's desk is told under.

@details `INotifier` makes one cause one message (`src/core/contracts/i_notifier.py`):
the same cause told again updates its message box or bar, a recovery clears
it. A desk exists per venue, so the venue is part of the key: Spot's outage
and Futures' are two messages. The key reads the venue's identifier, which a
UI file may not show as text (`test_venues_are_shown_by_title.py`), so it is
built here, where an identifier is a key and not words on a screen.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def failure_cause(venue: TradingVenue, *parts: str) -> str:
    """@return `trading.<venue>.<part>.<part>...`, e.g.
    `trading.futures_testnet.account_tabs`."""
    return ".".join(("trading", venue.value, *parts))
