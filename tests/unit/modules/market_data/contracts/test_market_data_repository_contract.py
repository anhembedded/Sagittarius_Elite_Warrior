"""The market-data repository contract, against the verified fake (HLD §10.3).

The fake's half. The real `SQLAlchemyMarketDataRepository` runs the identical
assertions in
`tests/integration/modules/market_data/contracts/test_market_data_repository_real.py`,
which is what makes this fake *verified* rather than merely in-memory.
"""

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.contract_market_data_repository import (
    MarketDataRepositoryContract,
    candle,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)


class TestFakeMarketDataRepository(MarketDataRepositoryContract):
    @pytest.fixture
    def impl(self) -> IMarketDataRepository:
        return FakeMarketDataRepository()


def test_the_seed_argument_stores_like_a_save() -> None:
    """The fake's one addition to the port: arranging history in a line. It
    must behave exactly as `save_klines()` does, upsert included, or the
    shortcut would let a consumer test against a store the real repository
    could never hold."""
    repo = FakeMarketDataRepository(
        [candle(minutes=0, close_price=1.0), candle(minutes=0, close_price=2.0)]
    )

    rows = repo.get_klines("BTCUSDT", TimeFrame.ONE_MINUTE)

    assert len(rows) == 1, "the seed must upsert, not append"
    assert rows[0].close_price == 2.0


def test_vacuum_is_recorded_so_a_caller_can_prove_it_asked() -> None:
    """There is no file to rewrite in memory, but a maintenance path that must
    prove it ran needs something to assert against — a silent no-op gives it
    nothing."""
    repo = FakeMarketDataRepository()

    repo.vacuum("BTCUSDT")
    repo.vacuum()

    assert repo.vacuum_calls == ["BTCUSDT", None]


def test_purge_all_reports_how_much_it_removed() -> None:
    repo = FakeMarketDataRepository(
        [candle("BTCUSDT", 0), candle("BTCUSDT", 1), candle("ETHUSDT", 0)]
    )

    assert repo.purge_all() == 3
    assert repo.list_available_shards() == []
