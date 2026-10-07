"""`EPIC-028O` — `IMarkPriceReader` for USD-M Futures:
`GET /fapi/v1/premiumIndex?symbol=`, unsigned.

@details Answers `{symbol, markPrice, indexPrice, estimatedSettlePrice,
lastFundingRate, interestRate, nextFundingTime, time}` for one symbol, per
Binance's documented USD-M API; not re-verified against a live call (egress
to `*.binance.*` is blocked in this sandbox). Only the mark price and its
time are read.
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_mark_price_reader import (
    IMarkPriceReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.mark_price import (
    MarkPrice,
)


class FuturesMarkPriceReader(IMarkPriceReader):
    """Reads one symbol's mark price on its Futures venue."""

    def __init__(self, session_factory: FuturesSessionFactory) -> None:
        self._session_factory = session_factory

    def mark_price(self, symbol: str) -> MarkPrice:
        with market_price_answer(f"{symbol} Futures mark price"):
            client = self._session_factory.create_futures_metadata_client()
            return _mark_price(client.futures_mark_price(symbol=symbol), symbol)


def _mark_price(answer: dict[str, Any], symbol: str) -> MarkPrice:
    if answer["symbol"] != symbol:
        raise ValueError(f"premiumIndex answered {answer['symbol']}, not {symbol}")
    return MarkPrice(
        symbol=symbol,
        mark_price=Decimal(str(answer["markPrice"])),
        as_of=datetime.fromtimestamp(int(answer["time"]) / 1000, tz=UTC),
    )
