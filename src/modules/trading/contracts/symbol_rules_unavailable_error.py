"""`EPIC-028H` — a venue has no order filters for a symbol."""

from __future__ import annotations


class SymbolRulesUnavailableError(LookupError):
    """Raised when a venue's symbol catalog does not list the symbol, even
    after a fresh fetch. Never answered with default filters: a guessed lot
    step would size an order the exchange refuses."""
