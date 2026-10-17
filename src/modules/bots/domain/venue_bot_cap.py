"""`EPIC-029J` J1b — how many bots may be active on one venue at once (ADR D20).

Two bots on different symbols of a venue run together; the symbol lease keeps two off one
symbol. The count is bounded because everything the bots of a venue spend is spent from one
account: its request weight, its order rate and its margin. The cap is **per venue** (a `TradingVenue`: Spot or Futures, mainnet or testnet), not per
account: one mainnet account may run five Spot and five Futures bots, which spend separate
weight, order and margin budgets. The figure comes from the measured
fan-out, request weight and order rate (`EPIC-029J1b` §5a) and is the owner's decision, since it
sets how much money one account can have working at once. It is a code constant and not a
setting: raising it is a reviewed change next to the numbers that justify it.
"""

from __future__ import annotations

#: The most bots, not at rest, one venue holds. The owner chose 5 on 2026-10-17 (*"5 bot, ngân sách
#: riêng từng bot"*), with each bot keeping its own budget and no sum cap.
MAX_ACTIVE_BOTS_PER_VENUE = 5
