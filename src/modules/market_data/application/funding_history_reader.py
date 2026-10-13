"""`IFundingHistory` over the venue's exchange client (`EPIC-039K`).

@details Only a USD-M perpetual has funding, so any other market is answered with
`FundingHistoryUnavailableError` and a sentence saying so, never an empty history: an empty
answer would read as "nothing was charged". The client is asked for lazily, because
building one is a network call (`BUG-045`).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.funding_event import (
    FundingEvent,
    FundingHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_funding_history import (
    IFundingHistory,
)


class ExchangeFundingHistory(IFundingHistory):
    """Reads the funding history from the exchange the venue's client talks to."""

    def __init__(self, client: Callable[[], IExchangeClient]) -> None:
        self._client = client

    def funding_between(
        self,
        market: MarketType,
        symbol: str,
        start: datetime,
        end: datetime,
        cancelled: Callable[[], bool],
    ) -> tuple[FundingEvent, ...]:
        if market is not MarketType.FUTURES_USD_M:
            raise FundingHistoryUnavailableError(
                "Only a USDⓈ-M Futures perpetual has funding; this market has none."
            )
        return tuple(
            self._client().get_funding_rate_history(symbol, start, end, cancelled)
        )
