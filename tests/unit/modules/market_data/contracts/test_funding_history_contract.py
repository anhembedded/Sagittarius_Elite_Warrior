"""The contract suite for `IFundingHistory` (HLD §10.3, `EPIC-039K`).

Both implementations run it: `FakeFundingHistory`, and the real `ExchangeFundingHistory` over
a `PythonBinanceClient` whose SDK answers the same records, so the fake cannot promise what
the reader does not.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.client import (
    PythonBinanceClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.funding_history_reader import (
    ExchangeFundingHistory,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.funding_event import (
    FundingEvent,
    FundingHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_funding_history import (
    IFundingHistory,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_funding_history import (
    FakeFundingHistory,
)

_FUTURES = MarketType.FUTURES_USD_M
_T = [datetime(2024, 1, 1, h, tzinfo=UTC) for h in (0, 8, 16)]
_EVENTS = [
    FundingEvent("BTCUSDT", moment, Decimal("0.0001"), Decimal(42000)) for moment in _T
]


def _never() -> bool:
    return False


class FundingHistoryContract:
    """Inherit this and provide `impl`, seeded with `_EVENTS` for BTCUSDT."""

    @pytest.fixture
    def impl(self) -> IFundingHistory:
        raise NotImplementedError

    def test_bounds_are_inclusive_and_the_answer_is_oldest_first(
        self, impl: IFundingHistory
    ) -> None:
        got = impl.funding_between(_FUTURES, "BTCUSDT", _T[0], _T[1], _never)

        assert [event.time for event in got] == [_T[0], _T[1]]

    def test_a_period_with_no_settlement_is_empty(self, impl: IFundingHistory) -> None:
        empty = datetime(2024, 1, 1, 1, tzinfo=UTC)

        assert impl.funding_between(_FUTURES, "BTCUSDT", empty, empty, _never) == ()

    def test_spot_has_no_funding_and_says_so_instead_of_answering_empty(
        self, impl: IFundingHistory
    ) -> None:
        with pytest.raises(FundingHistoryUnavailableError, match="has none"):
            impl.funding_between(MarketType.SPOT, "BTCUSDT", _T[0], _T[2], _never)


class TestFakeFundingHistory(FundingHistoryContract):
    @pytest.fixture
    def impl(self) -> IFundingHistory:
        return FakeFundingHistory(_EVENTS)


class TestExchangeFundingHistory(FundingHistoryContract):
    @pytest.fixture
    def impl(self) -> IFundingHistory:
        sdk = Mock()

        def answer(**params: int) -> list[dict[str, object]]:
            return [
                {
                    "symbol": "BTCUSDT",
                    "fundingRate": "0.0001",
                    "fundingTime": int(event.time.timestamp() * 1000),
                    "markPrice": "42000",
                }
                for event in _EVENTS
                if params["startTime"]
                <= event.time.timestamp() * 1000
                <= params["endTime"]
            ]

        sdk.futures_funding_rate.side_effect = answer
        return ExchangeFundingHistory(lambda: PythonBinanceClient(client=sdk))
