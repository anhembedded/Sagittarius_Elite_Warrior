"""`EPIC-028H` — `IOrderEntryTerms`' verified fake.

An unconfigured fake raises `SymbolRulesUnavailableError`, the real
adapter's answer for a symbol its venue does not list, so a test that forgot
to seed terms fails rather than sizing orders against invented filters.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_entry_terms import (
    IOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_entry_terms import (
    OrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_rules_unavailable_error import (
    SymbolRulesUnavailableError,
)


class FakeOrderEntryTerms(IOrderEntryTerms):
    """The terms a test says each symbol has."""

    def __init__(self, *terms: OrderEntryTerms) -> None:
        self._terms = {entry.rules.symbol: entry for entry in terms}
        #: A network read on the real adapter; a panel reading it per
        #: keystroke is a defect a test should be able to see.
        self.reads: list[str] = []

    def terms_for(self, symbol: str) -> OrderEntryTerms:
        self.reads.append(symbol)
        terms = self._terms.get(symbol)
        if terms is None:
            raise SymbolRulesUnavailableError(f"no terms seeded for {symbol}")
        return terms
