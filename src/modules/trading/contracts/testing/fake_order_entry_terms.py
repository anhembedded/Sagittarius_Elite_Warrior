"""`EPIC-028H` — `IOrderEntryTerms`' verified fake.

An unconfigured fake raises `SymbolRulesUnavailableError`, the real
adapter's answer for a symbol its venue does not list, so a test that forgot
to seed terms fails rather than sizing orders against invented filters.

`EPIC-028O` — the other reads are seeded per symbol through `FuturesReads`
and `books`. An unseeded read raises the port's own error for an exchange
that did not answer, never a default figure. A Spot test seeds
`FuturesReads.not_applicable()`, which is what the real service answers on
Spot.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_unavailable_error import (
    AccountControlUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_entry_terms import (
    IOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.mark_price import (
    MarkPrice,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.market_price_unavailable_error import (
    MarketPriceRateLimitedError,
    MarketPriceUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_entry_terms import (
    OrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_rules_unavailable_error import (
    SymbolRulesUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    DEFAULT_TRADING_LIMITS,
)

#: The app's own fallback limit, so a test that does not care about the
#: limit sees the figure the composition root would use.
DEFAULT_ORDER_NOTIONAL_LIMIT = DEFAULT_TRADING_LIMITS.max_notional_per_order


@dataclass(frozen=True)
class FuturesReads:
    """What the three Futures-only reads answer, per symbol."""

    settings: Mapping[str, FuturesSymbolSetting | NotApplicable] = field(
        default_factory=dict
    )
    brackets: Mapping[str, LeverageBrackets | NotApplicable] = field(
        default_factory=dict
    )
    marks: Mapping[str, MarkPrice | NotApplicable] = field(default_factory=dict)

    @classmethod
    def not_applicable(cls, *symbols: str) -> FuturesReads:
        """A Spot venue's answers for `symbols`."""
        none = NotApplicable.ON_THIS_VENUE
        return cls(
            settings=dict.fromkeys(symbols, none),
            brackets=dict.fromkeys(symbols, none),
            marks=dict.fromkeys(symbols, none),
        )


class FakeOrderEntryTerms(IOrderEntryTerms):
    """The terms a test says each symbol has."""

    def __init__(
        self,
        *terms: OrderEntryTerms,
        futures: FuturesReads | None = None,
        books: Mapping[str, BestBidAsk] | None = None,
        notional_limit: Decimal = DEFAULT_ORDER_NOTIONAL_LIMIT,
    ) -> None:
        self._terms = {entry.rules.symbol: entry for entry in terms}
        self._futures = futures or FuturesReads()
        self._books = dict(books or {})
        self._pauses: dict[str, timedelta] = {}
        self._notional_limit = notional_limit
        #: A network read on the real adapter; a panel reading it per
        #: keystroke is a defect a test should be able to see.
        self.reads: list[str] = []
        #: Book reads per symbol: a bot that must not trade on a stale price
        #: re-reads the book, and a test should be able to see that it did.
        self.book_reads: list[str] = []

    def terms_for(self, symbol: str) -> OrderEntryTerms:
        self.reads.append(symbol)
        terms = self._terms.get(symbol)
        if terms is None:
            raise SymbolRulesUnavailableError(f"no terms seeded for {symbol}")
        return terms

    def futures_setting_for(self, symbol: str) -> FuturesSymbolSetting | NotApplicable:
        answer = self._futures.settings.get(symbol)
        if answer is None:
            raise AccountControlUnavailableError(f"no setting seeded for {symbol}")
        return answer

    def leverage_brackets_for(self, symbol: str) -> LeverageBrackets | NotApplicable:
        answer = self._futures.brackets.get(symbol)
        if answer is None:
            raise AccountControlUnavailableError(f"no brackets seeded for {symbol}")
        return answer

    def mark_price_for(self, symbol: str) -> MarkPrice | NotApplicable:
        answer = self._futures.marks.get(symbol)
        if answer is None:
            raise MarketPriceUnavailableError(f"no mark price seeded for {symbol}")
        return answer

    def quote(self, book: BestBidAsk) -> None:
        """Move the book `book.symbol` answers from now on."""
        self._books[book.symbol] = book
        self._pauses.pop(book.symbol, None)

    def ask_for_a_pause(self, symbol: str, retry_after: timedelta) -> None:
        """`symbol`'s book answers a rate limit of `retry_after` until `quote`d."""
        self._books.pop(symbol, None)
        self._pauses[symbol] = retry_after

    def unquote(self, symbol: str) -> None:
        """`symbol`'s book is unreadable from now on."""
        self._books.pop(symbol, None)

    def best_bid_ask_for(self, symbol: str) -> BestBidAsk:
        self.book_reads.append(symbol)
        if symbol in self._pauses:
            raise MarketPriceRateLimitedError(
                f"no book for {symbol}: the exchange asked for a pause",
                self._pauses[symbol],
            )
        answer = self._books.get(symbol)
        if answer is None:
            raise MarketPriceUnavailableError(f"no book seeded for {symbol}")
        return answer

    def order_notional_limit(self) -> Decimal:
        return self._notional_limit
