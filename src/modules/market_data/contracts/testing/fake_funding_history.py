"""The verified fake for `IFundingHistory` (HLD §10.3, `EPIC-039K`).

**Who needs it.** The Futures Grid backtest asks for the funding a symbol settled over its
period, and `IFundingHistory` is a *foreign* port to the bots module, so
`Mock(spec=IFundingHistory)` is not an option (`test_no_foreign_port_is_mocked.py`).

**Scripted, with the real port's rules.** It answers the settlements a test gives it, filtered
to `start <= time <= end` (both inclusive, oldest first) and for the symbol asked; a market
without funding, or a script that says the exchange is down, raises
`FundingHistoryUnavailableError` as the real reader does. `test_funding_history_contract.py`
runs one suite against both this and `ExchangeFundingHistory`, so they cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.funding_event import (
    FundingEvent,
    FundingHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_funding_history import (
    IFundingHistory,
)


@dataclass(frozen=True, slots=True)
class FundingRead:
    """One `funding_between` call, as the caller made it."""

    market: MarketType
    symbol: str
    start: datetime
    end: datetime


class FakeFundingHistory(IFundingHistory):
    """Answers the scripted settlements, or the scripted failure."""

    def __init__(
        self,
        events: Sequence[FundingEvent] = (),
        *,
        unavailable: str | None = None,
    ) -> None:
        self._events = sorted(events, key=lambda event: event.time)
        self._unavailable = unavailable
        #: Every read, in order, so a test can see what a consumer asked for.
        self.reads: list[FundingRead] = []

    def funding_between(
        self,
        market: MarketType,
        symbol: str,
        start: datetime,
        end: datetime,
        cancelled: Callable[[], bool],
    ) -> tuple[FundingEvent, ...]:
        self.reads.append(FundingRead(market, symbol, start, end))
        if market is not MarketType.FUTURES_USD_M:
            raise FundingHistoryUnavailableError(
                "Only a USDⓈ-M Futures perpetual has funding; this market has none."
            )
        if self._unavailable is not None:
            raise FundingHistoryUnavailableError(self._unavailable)
        return tuple(
            event
            for event in self._events
            if event.symbol == symbol and start <= event.time <= end
        )
