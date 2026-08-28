"""Which symbols a picker shows, given what the user typed and clicked.

Pure functions over plain data, deliberately holding no widget: this is the
part that decides what the user sees, and it is the part that can be wrong
without anything crashing — a filter that silently drops a symbol looks
exactly like an exchange that does not list it. Keeping it out of the dialog
is what lets it be tested without a Qt event loop.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum

from .quote_asset import SymbolParts, split_symbol


class Scope(str, Enum):
    """Which pool of symbols the user is looking at."""

    ALL = "all"
    FAVOURITES = "favourites"
    RECENT = "recent"


#: The quote filter's own "no filter" value. A plain `None` would work, but
#: the tab bar needs something to key its buttons on, and a magic empty string
#: read as "symbols with no known quote" the first time it was written.
QUOTE_ANY = "*"

#: The quote filter tab standing for "any national currency" — one tab instead
#: of the eighteen entries in `FIAT_QUOTES`.
QUOTE_FIAT = "FIAT"


@dataclass(frozen=True)
class SymbolEntry:
    """One symbol as the picker needs it: split, and tagged with what the user
    has done with it before."""

    parts: SymbolParts
    is_favourite: bool
    is_recent: bool
    is_current: bool

    @property
    def symbol(self) -> str:
        return self.parts.symbol


@dataclass(frozen=True)
class FilterState:
    """Everything the user has set that narrows the list."""

    query: str = ""
    scope: Scope = Scope.ALL
    quote: str = QUOTE_ANY


def build_entries(
    symbols: Iterable[str],
    *,
    favourites: Iterable[str],
    recents: Iterable[str],
    current: str,
) -> list[SymbolEntry]:
    """Tags every symbol with its split and its history.

    Favourites and recents are compared case-insensitively against the
    exchange's own casing, so a value remembered from an older run (or typed
    into Dev Board's editable combo) still matches.
    """
    favourite_set = {value.upper() for value in favourites}
    recent_set = {value.upper() for value in recents}
    current_upper = current.upper()
    return [
        SymbolEntry(
            parts=split_symbol(symbol),
            is_favourite=symbol.upper() in favourite_set,
            is_recent=symbol.upper() in recent_set,
            is_current=symbol.upper() == current_upper,
        )
        for symbol in symbols
    ]


def _matches_quote(entry: SymbolEntry, quote: str) -> bool:
    if quote == QUOTE_ANY:
        return True
    if quote == QUOTE_FIAT:
        return entry.parts.is_fiat
    return entry.parts.quote == quote


def _matches_scope(entry: SymbolEntry, scope: Scope) -> bool:
    if scope is Scope.FAVOURITES:
        return entry.is_favourite
    if scope is Scope.RECENT:
        return entry.is_recent
    return True


def _matches_query(entry: SymbolEntry, needle: str) -> bool:
    return needle in entry.symbol.upper()


def apply_filter(
    entries: Sequence[SymbolEntry], state: FilterState
) -> list[SymbolEntry]:
    """The entries left after every active filter, in the order given.

    All three filters are ANDed. Search is a plain substring match on the whole
    symbol rather than on the base alone: typing "usdt" to see every USDT pair
    is at least as common as typing "eth" to find one coin, and the quote tabs
    are the precise way to do the former.
    """
    needle = state.query.strip().upper()
    return [
        entry
        for entry in entries
        if _matches_scope(entry, state.scope)
        and _matches_quote(entry, state.quote)
        and (not needle or _matches_query(entry, needle))
    ]


def partition_favourites(
    entries: Sequence[SymbolEntry],
) -> tuple[list[SymbolEntry], list[SymbolEntry]]:
    """Splits already-filtered entries into (favourites, the rest).

    The dialog renders favourites in their own section above the results, so
    a starred symbol is one glance away instead of somewhere in a
    fourteen-hundred-entry grid. Deliberately operates on the FILTERED list:
    a favourite that does not match the current search must not reappear at
    the top, which is what searching is for.
    """
    favourites = [entry for entry in entries if entry.is_favourite]
    rest = [entry for entry in entries if not entry.is_favourite]
    return favourites, rest


def available_quotes(entries: Sequence[SymbolEntry]) -> list[str]:
    """The quote-filter values worth offering, given what is actually listed.

    Offering a `BTC` tab that yields nothing is worse than not offering it, so
    this reports only quotes present in `entries` — plus `FIAT` whenever any
    national-currency pair exists at all. Ordered by how many symbols each
    covers, so the tabs a user reaches for sit leftmost.
    """
    counts: dict[str, int] = {}
    has_fiat = False
    for entry in entries:
        if not entry.parts.has_known_quote:
            continue
        if entry.parts.is_fiat:
            has_fiat = True
            continue
        counts[entry.parts.quote] = counts.get(entry.parts.quote, 0) + 1

    ranked = sorted(counts, key=lambda quote: (-counts[quote], quote))
    return ranked + ([QUOTE_FIAT] if has_fiat else [])
