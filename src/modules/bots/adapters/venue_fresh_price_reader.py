"""`EPIC-035I` — `IFreshPriceReader` over the venue's published trading ports."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_fresh_price_reader import (
    FreshPriceUnavailableError,
    IFreshPriceReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.market_price_unavailable_error import (
    MarketPriceRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class VenueFreshPriceReader(IFreshPriceReader):
    """The middle of the best bid and ask, as a bot's own market price is read."""

    def __init__(self, ports: IVenueTradingPorts) -> None:
        self._ports = ports

    def read(self, venue: TradingVenue, symbol: str) -> Decimal:
        try:
            book = self._ports.get(venue).order_entry_terms.best_bid_ask_for(symbol)
        except MarketPriceRateLimitedError as limited:
            raise FreshPriceUnavailableError(
                f"{venue.value} {symbol}: the exchange asked for a pause",
                limited.retry_after,
            ) from limited
        # Converted at the seam: every way the venue can fail to answer (the
        # network, the gateway's page, an unlisted symbol) is one named fault
        # for the caller, which retries and never inspects the cause.
        except Exception as exc:
            raise FreshPriceUnavailableError(
                f"{venue.value} {symbol}: {type(exc).__name__}"
            ) from exc
        return (book.bid_price + book.ask_price) / 2
