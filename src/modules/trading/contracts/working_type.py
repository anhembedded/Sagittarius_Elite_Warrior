"""`EPIC-039L` — which price a conditional order's trigger is compared against.

@details Binance's `workingType` (`CONTRACT_PRICE`, the last traded price, or `MARK_PRICE`).
The desk's stops are judged on the last price, the price its own trigger check uses
(`futures_algo_order_mapper.py`), so that stays the default and no existing order changes. A
bot's protective stop is judged on the mark price, because a Futures position is liquidated on
the mark (design 039 §7; `DECISION_2026-10-16` D3).

Plausible extensions, each a local change: another reference price Binance adds is one more
member and one more line in the mapper's table.
"""

from __future__ import annotations

from enum import Enum


class WorkingType(str, Enum):
    """The price a conditional order triggers on."""

    #: The last traded price (Binance `CONTRACT_PRICE`): what every order here used before.
    LAST_PRICE = "contract_price"
    #: The mark price (Binance `MARK_PRICE`): what a position's liquidation is judged on.
    MARK_PRICE = "mark_price"
