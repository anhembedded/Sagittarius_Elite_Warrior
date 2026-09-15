"""`ITradingAccountReader`'s contract, against its verified fake (HLD §10.3).

The real `FuturesAccountReader` runs the same suite against the fake exchange
server once the handler registrations move into the module with the factory it
shares with `market_data` — see the suite's own docstring.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
    MarginType,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.contract_trading_account_reader import (
    GivenStatus,
    TradingAccountReaderContract,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_account_reader import (
    FakeTradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@pytest.fixture
def ready_status() -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=True,
        failure=None,
        server_time_skew_ms=10,
        usdt_balance=Decimal(1000),
        position_mode=PositionMode.ONE_WAY,
        margin_type=MarginType.CROSSED,
        open_position_count=0,
    )


@pytest.fixture
def unreachable_status() -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=False,
        failure=ConnectionFailureKind.BAD_SIGNATURE,
        server_time_skew_ms=None,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=None,
    )


class TestTheFake(TradingAccountReaderContract):
    @pytest.fixture
    def impl(self) -> FakeTradingAccountReader:
        return FakeTradingAccountReader()

    @pytest.fixture
    def given_status(self, impl: FakeTradingAccountReader) -> GivenStatus:
        def answer(status: ExchangeConnectionStatus) -> None:
            impl.answer_with(status)

        return answer


class TestTheFakesOwnBookkeeping:
    """`BUG-120` — what the fake adds beyond the port is tested too."""

    def test_it_counts_the_checks(self, ready_status: ExchangeConnectionStatus) -> None:
        """The real check is a network round trip, so a caller doing it per
        candle is a defect a test should be able to see."""
        fake = FakeTradingAccountReader(ready_status)

        fake.check_connection()
        fake.check_connection()

        assert fake.checks == 2

    def test_an_unconfigured_fake_reports_not_configured_not_success(self) -> None:
        """A fake whose default is "everything is fine" makes a test that
        forgot to seed pass for the wrong reason."""
        answer = FakeTradingAccountReader().check_connection()

        assert answer.reachable is False
        assert answer.failure is ConnectionFailureKind.NOT_CONFIGURED
