"""`EPIC-039G` — `IFundingReader` for USD-M Futures: `GET /fapi/v1/premiumIndex?symbol=`,
unsigned.

@details The same answer `FuturesMarkPriceReader` reads (`lastFundingRate` "the Latest
funding rate", `nextFundingTime` "Next Funding Time", `time`), per Binance's page read
2026-10-13; not re-verified against a live call (egress to `*.binance.*` is blocked in this
sandbox). A symbol with no funding rate (a delivery contract answers an empty string) is an
unavailable read, never a rate of zero.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_session_factory import (
    FuturesSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.market_price_reads import (
    market_price_answer,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.funding_rate import (
    FundingRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_funding_reader import (
    IFundingReader,
)


class FuturesFundingReader(IFundingReader):
    """Reads one symbol's funding rate on its Futures venue."""

    def __init__(self, session_factory: FuturesSessionFactory) -> None:
        self._session_factory = session_factory

    def funding_rate(self, symbol: str) -> FundingRate:
        with market_price_answer(f"{symbol} Futures funding rate"):
            client = self._session_factory.create_futures_metadata_client()
            return _funding_rate(client.futures_mark_price(symbol=symbol), symbol)


def _funding_rate(answer: dict[str, Any], symbol: str) -> FundingRate:
    if answer["symbol"] != symbol:
        raise ValueError(f"premiumIndex answered {answer['symbol']}, not {symbol}")
    rate = answer.get("lastFundingRate")
    if rate in (None, ""):
        raise ValueError(f"premiumIndex gave {symbol} no funding rate")
    return FundingRate(
        symbol=symbol,
        rate=Decimal(str(rate)),
        next_funding_at=datetime.fromtimestamp(
            int(answer["nextFundingTime"]) / 1000, tz=UTC
        ),
        as_of=datetime.fromtimestamp(int(answer["time"]) / 1000, tz=UTC),
    )
