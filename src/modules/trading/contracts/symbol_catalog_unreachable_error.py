"""`EPIC-035U` — the venue's symbol catalog could not be read, which says nothing about the symbol.

A `SymbolRulesUnavailableError` means "the venue does not list the symbol" for
a caller that reads it as a delisting. A timeout or a refused request is also
raised that way by the catalog fetch, so a caller that must tell the two apart
(a running bot that halts for a delisting, never for a bad moment) catches this
subclass first.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_rules_unavailable_error import (
    SymbolRulesUnavailableError,
)


class SymbolCatalogUnreachableError(SymbolRulesUnavailableError):
    """The catalog fetch failed in transit; whether the symbol is listed is unknown."""
