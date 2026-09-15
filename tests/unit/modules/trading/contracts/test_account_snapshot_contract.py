"""`IAccountSnapshot`'s contract, against its verified fake (HLD §10.3).

The real `AccountSnapshotService` runs the same suite once PR 1.3c moves the
query handlers' registrations into the module — they reach the venue through
the `ExchangeSessionFactory` instance still shared with `market_data`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
    MarginType,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.contract_account_snapshot import (
    AccountSnapshotContract,
    GivenAccount,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
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
        server_time_skew_ms=8,
        usdt_balance=Decimal(2500),
        position_mode=PositionMode.ONE_WAY,
        margin_type=MarginType.CROSSED,
        open_position_count=0,
    )


@pytest.fixture
def unreachable_status() -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=False,
        failure=ConnectionFailureKind.CLOCK_SKEW,
        server_time_skew_ms=90_000,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=None,
    )


def _position(symbol: str) -> LivePosition:
    return LivePosition(
        symbol=symbol,
        position_amt=Decimal("0.01"),
        entry_price=Decimal(64000),
        mark_price=Decimal(64100),
        unrealized_pnl=Decimal(1),
        leverage=5,
        margin_type=MarginType.CROSSED,
        liquidation_price=None,
        updated_at=datetime(2026, 9, 15, tzinfo=UTC),
    )


class TestTheFake(AccountSnapshotContract):
    @pytest.fixture
    def impl(self) -> FakeAccountSnapshot:
        return FakeAccountSnapshot()

    @pytest.fixture
    def given_account(self, impl: FakeAccountSnapshot) -> GivenAccount:
        def seed(status: ExchangeConnectionStatus) -> None:
            impl.answer_with(status)

        return seed


class TestTheFakesOwnBookkeeping:
    """`BUG-120` — the helpers the fake adds beyond the port."""

    def test_holding_replaces_rather_than_appends(self) -> None:
        """The real read is a fresh account snapshot, so a position the venue
        closed stops being reported. A fake that accumulated would keep
        reporting it and a caller's "position closed" branch would never run."""
        fake = FakeAccountSnapshot()

        fake.holding([_position("BTCUSDT")])
        assert [p.symbol for p in fake.open_positions()] == ["BTCUSDT"]

        fake.holding([_position("ETHUSDT")])
        assert [p.symbol for p in fake.open_positions()] == ["ETHUSDT"]

    def test_it_counts_the_two_reads_separately(self) -> None:
        """Both are network round trips on the real adapter, and a caller
        doing either per candle is a defect a test should be able to see."""
        fake = FakeAccountSnapshot()

        fake.check_connection()
        fake.open_positions()
        fake.open_positions()

        assert (fake.connection_checks, fake.position_reads) == (1, 2)

    def test_an_unconfigured_fake_reports_not_configured_not_success(self) -> None:
        answer = FakeAccountSnapshot().check_connection()

        assert answer.reachable is False
        assert answer.failure is ConnectionFailureKind.NOT_CONFIGURED
