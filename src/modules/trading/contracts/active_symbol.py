"""`BOT-149` — a pair a history of "every symbol" covers, and why it is active.

@details A reader names its active pairs and says why each is one, so the
application layer, not the adapter, decides which pairs an every-pair page
reads first when it has to leave some out (`history_scope`). Order is policy;
the reason is the venue's fact.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class ActiveReason(Enum):
    """Why a pair is active, strongest first: a pair that is several of these
    carries the earliest listed."""

    OPEN_ORDER = "open order"
    TRADED = "traded"
    HELD = "held"


@dataclass(frozen=True)
class ActiveSymbol:
    """One active pair and the strongest reason the venue has for it."""

    symbol: str
    reason: ActiveReason


_STRENGTH = {reason: rank for rank, reason in enumerate(ActiveReason)}


def active_symbols_from(
    reasons: Iterable[tuple[ActiveReason, Iterable[str]]],
) -> tuple[ActiveSymbol, ...]:
    """@brief Each pair once, with its strongest reason, sorted by symbol.
    @param reasons Each reason with the pairs it applies to."""
    strongest: dict[str, ActiveReason] = {}
    for reason, symbols in reasons:
        for symbol in symbols:
            known = strongest.get(symbol)
            if known is None or _STRENGTH[reason] < _STRENGTH[known]:
                strongest[symbol] = reason
    return tuple(ActiveSymbol(s, strongest[s]) for s in sorted(strongest))
