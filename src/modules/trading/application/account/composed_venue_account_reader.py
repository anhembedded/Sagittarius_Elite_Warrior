"""`EPIC-034D` — `IVenueAccountReader` for a venue that trades, composed from
the read ports it already has.

@details Four existing reads make one snapshot: the account (balances and the
`canTrade` flag), the venue's commission rates, the symbol's filters and the
book's price. Nothing here is new at the exchange; the new thing is that they
are read together and any one failing is a named `ConnectFailure`, never a
half-filled snapshot (`code/errors.md` #7). The reads are the same ports the
order desks use, so the Connect step reads exactly what an order will be
judged by.

It holds the read ports only: it cannot place, test or cancel an order.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate_unavailable_error import (
    CommissionRateUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_account_reader import (
    IVenueAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.market_price_unavailable_error import (
    MarketPriceUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_rules_unavailable_error import (
    SymbolRulesUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)

logger = logging.getLogger("App.VenueAccount")

#: Phase 1 trades USDT-quoted pairs only (`EPIC-027H` ADR D9).
QUOTE_ASSET = "USDT"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ComposedVenueAccountReader(IVenueAccountReader):
    def __init__(
        self,
        source: AccountSource,
        context: VenueContext,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._source = source
        self._context = context
        self._clock = clock

    @property
    def source(self) -> AccountSource:
        return self._source

    def read(self, symbol: str) -> VenueAccountSnapshot | ConnectFailure:
        status = self._context.account_reader.check_connection()
        if status.failure is not None or not status.reachable:
            return self._failed(
                status.failure or ConnectionFailureKind.NETWORK, "the account"
            )
        available = _available_of(status)
        if available is None:
            return self._failed(ConnectionFailureKind.NETWORK, "the balance")
        commission = self._commission(symbol)
        if isinstance(commission, ConnectFailure):
            return commission
        rules = self._rules(symbol)
        if isinstance(rules, ConnectFailure):
            return rules
        book = self._price(symbol)
        if isinstance(book, ConnectFailure):
            return book
        return VenueAccountSnapshot(
            source=self._source,
            symbol=symbol,
            read_at=self._clock(),
            quote_asset=QUOTE_ASSET,
            available=available,
            holdings=tuple(h for h in (status.holdings or ()) if not h.is_dust),
            commission=commission,
            can_trade=status.can_trade,
            rules=rules,
            price=book.ask_price if book.has_ask else book.bid_price,
        )

    def _commission(self, symbol: str) -> CommissionRate | ConnectFailure:
        try:
            return self._context.commission_reader.commission_rate(symbol)
        except CommissionRateUnavailableError as exc:
            return self._failed(ConnectionFailureKind.NETWORK, "the commission", exc)

    def _rules(self, symbol: str) -> SymbolOrderMetadata | ConnectFailure:
        try:
            rules = self._context.metadata_provider.get_or_fetch(symbol)
        except SymbolRulesUnavailableError as exc:
            return self._failed(ConnectionFailureKind.NETWORK, "the filters", exc)
        if rules is None:
            return self._failed(
                ConnectionFailureKind.NETWORK, f"the filters: {symbol} is not listed"
            )
        return rules

    def _price(self, symbol: str) -> BestBidAsk | ConnectFailure:
        try:
            book = self._context.book_ticker_reader.best_bid_ask(symbol)
        except MarketPriceUnavailableError as exc:
            return self._failed(ConnectionFailureKind.NETWORK, "the price", exc)
        if not (book.has_ask or book.has_bid):
            return self._failed(
                ConnectionFailureKind.NETWORK, f"the price: {symbol} has no orders"
            )
        return book

    def _failed(
        self,
        kind: ConnectionFailureKind,
        what: str,
        cause: Exception | None = None,
    ) -> ConnectFailure:
        logger.info(
            "Connect %s: could not read %s -> %s%s [connect-step]",
            self._source.value,
            what,
            kind.name,
            f" ({cause})" if cause is not None else "",
        )
        return ConnectFailure(self._source, kind, what)


def _available_of(status: ExchangeConnectionStatus) -> Decimal | None:
    summary = status.summary
    return summary.available_balance if summary is not None else status.usdt_balance
