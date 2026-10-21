"""`EPIC-039H` — `IMarkSource` over the venue's `premiumIndex` (`IOrderEntryTerms.mark_price_for`)."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_mark_source import (
    IMarkSource,
    MarkReadError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_entry_terms import (
    IOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.market_price_unavailable_error import (
    MarketPriceUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.request_priority import (
    RequestPriority,
)


def read_mark_price(terms: IOrderEntryTerms, symbol: str) -> Decimal:
    """The venue's mark price of `symbol` now, read as a guard of the bot's exits, so it uses the
    venue's weight reserve (`BOT-224`). @raise MarkReadError it could not be read."""
    try:
        mark = terms.mark_price_for(symbol, RequestPriority.EXIT_GUARD)
    except MarketPriceUnavailableError as error:
        raise MarkReadError(f"{symbol}: {error}") from error
    if isinstance(mark, NotApplicable):
        raise MarkReadError(f"{symbol}: the venue reports no mark price")
    return mark.mark_price


class ExchangeMarkSource(IMarkSource):
    """The mark of the bot's symbol, read from the exchange now. What places an order judges on
    this one (the protective stop is checked against the mark it is placed on): a placement is a
    confirmation, and never takes the shared reading (`BOT-221`)."""

    def __init__(self, context: GridRunContext, ports: IVenueTradingPorts) -> None:
        self._context = context
        self._ports = ports

    def read(self) -> Decimal:
        definition = self._context.state.bot.definition
        terms = self._ports.get(definition.venue).order_entry_terms
        return read_mark_price(terms, definition.symbol)


class WatchedMarkSource(IMarkSource):
    """The mark of the bot's symbol for an idle watch: the reading its watches share when there
    is one (`BOT-221`, at most half a beat old, dropped by any order or fill of the symbol), else
    a read. The exit watch and the risk watch of one bot are two of these over the one reading."""

    def __init__(self, context: GridRunContext, ports: IVenueTradingPorts) -> None:
        self._context = context
        self._fresh = ExchangeMarkSource(context, ports)

    def read(self) -> Decimal:
        shared = self._context.gateway.account_reads.shared_mark
        return self._fresh.read() if shared is None else shared.current()
