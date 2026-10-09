"""`EPIC-028H` — port: the terms an order panel sizes an order against.

@details Bound to one venue, like every port in `VenueTradingPorts`: the
Spot desk's panel reads Spot filters and Spot fees, and cannot ask Futures
by accident.

`EPIC-028O` adds the reads the desks' maxima and price buttons need. Each is
its own method because each changes at its own pace: the leverage and the
brackets when the user changes them, the mark price and the book every
second, the app's notional limit only with the configuration. On a venue
with no leverage, brackets or mark price (Spot) those three answer
`NotApplicable.ON_THIS_VENUE`, never an invented figure.

Plausible extensions, each one new method here plus its query:
- the funding rate and next funding time for the Futures desk header;
- the Multi-Assets mode, which changes what the Futures available balance
  counts;
- a mainnet venue, which needs nothing here: another `VenueTradingPorts`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.mark_price import (
    MarkPrice,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_entry_terms import (
    OrderEntryTerms,
)


class IOrderEntryTerms(ABC):
    """The filters, fees, prices and limits one venue applies to a symbol.

    Every method but `order_notional_limit` is a network read, so a caller
    runs it off the UI thread."""

    @abstractmethod
    def terms_for(self, symbol: str) -> OrderEntryTerms:
        """Read `symbol`'s order filters and the account's fee rates on it.

        A network read the first time a venue's catalog is needed, and for
        the fee every time.
        @raise SymbolRulesUnavailableError The venue does not list `symbol`.
        @raise CommissionRateUnavailableError The fee read failed.
        """

    @abstractmethod
    def fresh_terms_for(self, symbol: str) -> OrderEntryTerms:
        """`terms_for`, with the symbol's filters read from the exchange again
        instead of the venue's cached catalog (`EPIC-035U`): what a long run
        asks to learn that a tick size, a step or a status changed.
        @raise SymbolRulesUnavailableError The venue does not list `symbol`.
        @raise CommissionRateUnavailableError The fee read failed.
        """

    @abstractmethod
    def futures_setting_for(self, symbol: str) -> FuturesSymbolSetting | NotApplicable:
        """Read `symbol`'s current leverage and margin mode.
        @raise AccountControlRejectedError The exchange refused the read.
        @raise AccountControlUnavailableError The exchange never answered.
        """

    @abstractmethod
    def leverage_brackets_for(self, symbol: str) -> LeverageBrackets | NotApplicable:
        """Read `symbol`'s notional and leverage brackets.
        @raise AccountControlRejectedError The exchange refused the read.
        @raise AccountControlUnavailableError The exchange never answered.
        """

    @abstractmethod
    def mark_price_for(self, symbol: str) -> MarkPrice | NotApplicable:
        """Read `symbol`'s mark price.
        @raise MarketPriceUnavailableError The exchange did not answer.
        """

    @abstractmethod
    def best_bid_ask_for(self, symbol: str) -> BestBidAsk:
        """Read the best bid and ask on `symbol`'s book.
        @raise MarketPriceUnavailableError The exchange did not answer.
        """

    @abstractmethod
    def order_notional_limit(self) -> Decimal:
        """The largest notional the app lets one order have; an order over it
        is refused by the app's own gate before it is sent."""
