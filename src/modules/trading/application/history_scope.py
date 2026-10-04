"""`BUG-145` — which pairs one history page reads, bounded by request weight.

@details Binance reads a history one pair at a time, so an every-pair page
costs one read per pair the reader names as active. On Spot that is every
held asset's USDT pair: a Spot Testnet account holds about five hundred, and
a seven-day span is eight windows of weight 20 per pair and per endpoint, so
one desk opening asked for some 160 000 weight against Binance's 6 000 a
minute, answered `-1003`, and starved every other read, the commission rate a
bot's Start needs included. An every-pair page therefore reads at most
`EVERY_SYMBOL_SCAN_LIMIT` pairs, in the reader's own order, and says which
were left out rather than implying the whole account.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    IAccountHistoryReader,
)

#: Five Spot pairs over seven days cost 5 x 8 windows x weight 20 per
#: endpoint: 800, both tabs 1 600 of Binance's 6 000 a minute.
EVERY_SYMBOL_SCAN_LIMIT = 5


@dataclass(frozen=True)
class HistoryScope:
    """The pairs a page reads, and what it says about the ones it did not."""

    symbols: tuple[str, ...]
    notices: tuple[str, ...] = ()


def history_scope(
    reader: IAccountHistoryReader, symbol: str | None, since: datetime
) -> HistoryScope:
    """@return `symbol` alone, or at most `EVERY_SYMBOL_SCAN_LIMIT` of the
    pairs `reader` names as active since `since`."""
    if symbol:
        return HistoryScope((symbol,))
    active = reader.active_symbols(since)
    if len(active) <= EVERY_SYMBOL_SCAN_LIMIT:
        return HistoryScope(active)
    return HistoryScope(
        active[:EVERY_SYMBOL_SCAN_LIMIT],
        (
            (
                f"Read {EVERY_SYMBOL_SCAN_LIMIT} of {len(active)} active pairs, to "
                "stay within Binance's request weight; tick 'Hide other pairs' to "
                "read the desk's pair."
            ),
        ),
    )
