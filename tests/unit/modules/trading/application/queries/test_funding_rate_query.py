"""`EPIC-039G` — a Futures venue answers its funding rate; Spot, which has none, answers
`NotApplicable` and never a zero rate; a reading the exchange left blank is unavailable,
not zero."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_funding_reader import (
    FuturesFundingReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_funding_rate import (
    GetFundingRateQuery,
    GetFundingRateQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.funding_rate import (
    FundingRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_funding_reader import (
    IFundingReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.market_price_unavailable_error import (
    MarketPriceUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_AT = datetime(2026, 10, 13, 8, tzinfo=UTC)
_RATE = FundingRate("ETHUSDT", Decimal("0.0001"), _AT, _AT)


class _Funding(IFundingReader):
    def funding_rate(self, symbol: str) -> FundingRate:
        return replace(_RATE, symbol=symbol)


def _contexts() -> FakeVenueContexts:
    return FakeVenueContexts(
        replace(
            fake_venue_context(TradingVenue.FUTURES_TESTNET), funding_reader=_Funding()
        ),
        fake_venue_context(TradingVenue.SPOT_TESTNET),
    )


def test_futures_answers_the_funding_rate_of_its_symbol() -> None:
    answer = GetFundingRateQueryHandler(_contexts()).execute(
        GetFundingRateQuery(venue=TradingVenue.FUTURES_TESTNET, symbol="BTCUSDT")
    )

    assert answer == replace(_RATE, symbol="BTCUSDT")


def test_spot_has_no_funding_and_says_so_instead_of_a_zero_rate() -> None:
    answer = GetFundingRateQueryHandler(_contexts()).execute(
        GetFundingRateQuery(venue=TradingVenue.SPOT_TESTNET, symbol="BTCUSDT")
    )

    assert answer is NotApplicable.ON_THIS_VENUE


def _reader_answering(answer: dict[str, object]) -> FuturesFundingReader:
    sessions = Mock()
    sessions.create_futures_metadata_client.return_value.futures_mark_price.return_value = answer
    return FuturesFundingReader(sessions)


def _premium_index(**overrides: object) -> dict[str, object]:
    answer: dict[str, object] = {
        "symbol": "BTCUSDT",
        "markPrice": "64000.1",
        "lastFundingRate": "-0.00038246",
        "nextFundingTime": 1_597_392_000_000,
        "time": 1_597_370_495_002,
    }
    answer.update(overrides)
    return answer


def test_the_reader_keeps_the_sign_and_the_next_settlement_of_the_funding_rate() -> (
    None
):
    rate = _reader_answering(_premium_index()).funding_rate("BTCUSDT")

    assert rate.rate == Decimal("-0.00038246")
    assert rate.next_funding_at == datetime.fromtimestamp(1_597_392_000, tz=UTC)


@pytest.mark.parametrize("blank", ["", None])
def test_a_blank_funding_rate_is_unavailable_not_zero(blank: object) -> None:
    with pytest.raises(MarketPriceUnavailableError):
        _reader_answering(_premium_index(lastFundingRate=blank)).funding_rate("BTCUSDT")
