"""`EPIC-034E` — "what does the owner's mainnet key show".

The account is read for one symbol because a snapshot's filters and price are a
symbol's; the screen shows the account, so any listed symbol serves.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The symbol the mainnet view reads the filters and price of.
OVERVIEW_SYMBOL = "BTCUSDT"


@dataclass(frozen=True, slots=True)
class GetMainnetAccountQuery:
    symbol: str = OVERVIEW_SYMBOL
