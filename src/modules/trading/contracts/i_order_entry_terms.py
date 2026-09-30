"""`EPIC-028H` — port: the terms an order panel sizes an order against.

@details Bound to one venue, like every port in `VenueTradingPorts`: the
Spot desk's panel reads Spot filters and Spot fees, and cannot ask Futures
by accident.

Plausible extensions, each one new method here plus its query:
- the leverage brackets (`GET /fapi/v1/leverageBracket`), which the Futures
  panel's notional headroom needs (`EPIC-028I`);
- the best bid and ask for a "BBO" price button (`EPIC-028O`);
- a mainnet venue, which needs nothing here: another `VenueTradingPorts`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_entry_terms import (
    OrderEntryTerms,
)


class IOrderEntryTerms(ABC):
    """The filters and fees one venue applies to a symbol."""

    @abstractmethod
    def terms_for(self, symbol: str) -> OrderEntryTerms:
        """Read `symbol`'s order filters and the account's fee rates on it.

        A network read the first time a venue's catalog is needed, and for
        the fee every time, so a caller runs it off the UI thread.
        @raise SymbolRulesUnavailableError The venue does not list `symbol`.
        @raise CommissionRateUnavailableError The fee read failed.
        """
