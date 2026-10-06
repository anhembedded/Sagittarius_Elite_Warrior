"""`BUG-145` — which pairs one history page reads, bounded by request weight.

@details Binance reads a history one pair at a time, so an every-pair page
costs one read per pair the reader names as active. On Spot that is every
held asset's USDT pair: a Spot Testnet account holds about five hundred, and
a seven-day span is eight windows of weight 20 per pair and per endpoint, so
one desk opening asked for some 160 000 weight against Binance's 6 000 a
minute, answered `-1003`, and starved every other read, the commission rate a
bot's Start needs included. An every-pair page therefore reads at most the
reader's `every_symbol_scan_limit()` pairs, in the reader's own order, and
says which were left out rather than implying the whole account. The limit
is the venue's, because the cost per pair is: Futures reads seven days in one
window per pair and names only pairs actually in use, so it has none.

`BOT-149` — which pairs a capped page leaves out is this module's policy, not
the reader's alphabet: the pairs with an open order come first, then the
desk's own pair, then the pairs traded since, then the held assets, each group
in symbol order. A reader names the reason each pair is active
(`ActiveSymbol`) and nothing more. An uncapped page keeps symbol order.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.active_symbol import (
    ActiveReason,
    ActiveSymbol,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    IAccountHistoryReader,
)


@dataclass(frozen=True)
class HistoryScope:
    """The pairs a page reads, and what it says about the ones it did not."""

    symbols: tuple[str, ...]
    notices: tuple[str, ...] = ()


def history_scope(
    reader: IAccountHistoryReader,
    symbol: str | None,
    since: datetime,
    desk_symbol: str | None = None,
) -> HistoryScope:
    """@return `symbol` alone, or at most `reader.every_symbol_scan_limit()`
    of the pairs `reader` names as active since `since`, the user's own pairs
    first (see the module docstring)."""
    if symbol:
        return HistoryScope((symbol,))
    active = reader.active_symbols(since)
    limit = reader.every_symbol_scan_limit()
    if limit is None or len(active) <= limit:
        return HistoryScope(tuple(pair.symbol for pair in active))
    ordered = sorted(active, key=lambda pair: _priority(pair, desk_symbol))
    return HistoryScope(
        tuple(pair.symbol for pair in ordered[:limit]),
        (
            (
                f"Read {limit} of {len(active)} active pairs, to stay within "
                "Binance's request weight; tick 'Hide other pairs' to read the "
                "desk's pair."
            ),
        ),
    )


_AFTER_THE_DESK_PAIR = {
    ActiveReason.OPEN_ORDER: 0,
    ActiveReason.TRADED: 2,
    ActiveReason.HELD: 3,
}


def _priority(pair: ActiveSymbol, desk_symbol: str | None) -> tuple[int, str]:
    """Open order, then the desk's pair, then traded, then held; ties by symbol."""
    if pair.reason is ActiveReason.OPEN_ORDER:
        return (_AFTER_THE_DESK_PAIR[pair.reason], pair.symbol)
    if pair.symbol == desk_symbol:
        return (1, pair.symbol)
    return (_AFTER_THE_DESK_PAIR[pair.reason], pair.symbol)
