"""`EPIC-028F` — `GetCommissionRateQuery` answers from the addressed venue's
own reader."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_commission_rate import (
    GetCommissionRateQuery,
    GetCommissionRateQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_commission_rate_reader import (
    ICommissionRateReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class _FixedRates(ICommissionRateReader):
    def __init__(self, maker: str, taker: str) -> None:
        self._maker = Decimal(maker)
        self._taker = Decimal(taker)

    def commission_rate(self, symbol: str) -> CommissionRate:
        return CommissionRate(symbol, self._maker, self._taker)


def test_each_venue_answers_with_its_own_rates() -> None:
    contexts = FakeVenueContexts(
        replace(
            fake_venue_context(TradingVenue.FUTURES_TESTNET),
            commission_reader=_FixedRates("0.0002", "0.0005"),
        ),
        replace(
            fake_venue_context(TradingVenue.SPOT_TESTNET),
            commission_reader=_FixedRates("0.001", "0.001"),
        ),
    )
    handler = GetCommissionRateQueryHandler(contexts)

    spot = handler.execute(
        GetCommissionRateQuery(venue=TradingVenue.SPOT_TESTNET, symbol="BTCUSDT")
    )
    futures = handler.execute(
        GetCommissionRateQuery(venue=TradingVenue.FUTURES_TESTNET, symbol="BTCUSDT")
    )

    assert spot == CommissionRate("BTCUSDT", Decimal("0.001"), Decimal("0.001"))
    assert futures == CommissionRate("BTCUSDT", Decimal("0.0002"), Decimal("0.0005"))


def test_an_empty_symbol_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="symbol"):
        GetCommissionRateQuery(venue=TradingVenue.SPOT_TESTNET, symbol="")
