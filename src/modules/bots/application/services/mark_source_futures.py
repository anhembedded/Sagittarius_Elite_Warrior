"""`EPIC-039H` — `IMarkSource` over the venue's `premiumIndex` (`IOrderEntryTerms.mark_price_for`)."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_mark_source import (
    IMarkSource,
    MarkReadError,
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


class ExchangeMarkSource(IMarkSource):
    def __init__(self, context: GridRunContext, ports: IVenueTradingPorts) -> None:
        self._context = context
        self._ports = ports

    def read(self) -> Decimal:
        definition = self._context.state.bot.definition
        terms = self._ports.get(definition.venue).order_entry_terms
        try:
            mark = terms.mark_price_for(definition.symbol)
        except MarketPriceUnavailableError as error:
            raise MarkReadError(f"{definition.symbol}: {error}") from error
        if isinstance(mark, NotApplicable):
            raise MarkReadError(f"{definition.symbol}: the venue reports no mark price")
        return mark.mark_price
