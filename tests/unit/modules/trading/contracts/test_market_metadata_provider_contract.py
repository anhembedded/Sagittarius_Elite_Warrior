"""`IMarketMetadataProvider`'s contract, against its verified fake (HLD §10.3).

Only the fake runs it here, and the reason is written down rather than left as
a gap: the real `FuturesMetadataProvider` takes the `FuturesSessionFactory`
**instance** that `market_data` also uses, so it cannot be constructed in this
tier without a socket. `EPIC-025` PR 1.3b splits that factory one-per-context,
and the real half of this suite arrives with it, in
`tests/integration/modules/trading/contracts/`, against the fake exchange
server (HLD §10.3 rule 3: both implementations run the suite).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.contract_market_metadata_provider import (
    GivenMetadata,
    MarketMetadataProviderContract,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_market_metadata_provider import (
    FakeMarketMetadataProvider,
)


@pytest.fixture
def btc_metadata() -> FuturesSymbolMetadata:
    return FuturesSymbolMetadata(
        symbol="BTCUSDT",
        status="TRADING",
        step_size=Decimal("0.001"),
        tick_size=Decimal("0.01"),
        min_notional=Decimal(100),
        quantity_precision=3,
        price_precision=2,
        fetched_at=datetime(2026, 8, 27, tzinfo=UTC),
    )


class TestTheFake(MarketMetadataProviderContract):
    @pytest.fixture
    def impl(self) -> FakeMarketMetadataProvider:
        return FakeMarketMetadataProvider()

    @pytest.fixture
    def given_metadata(self, impl: FakeMarketMetadataProvider) -> GivenMetadata:
        def seed(metadata: Sequence[FuturesSymbolMetadata]) -> None:
            impl.seed(metadata)

        return seed


class TestTheFakesOwnBookkeeping:
    """What the fake adds beyond the port, which `BUG-120` established must be
    tested too: a helper no contract covers is a helper that can lie."""

    def test_it_records_every_symbol_it_was_asked_for(
        self, btc_metadata: FuturesSymbolMetadata
    ) -> None:
        fake = FakeMarketMetadataProvider([btc_metadata])

        fake.get_or_fetch("BTCUSDT")
        fake.get_or_fetch("nosuch")

        assert fake.reads == ["BTCUSDT", "nosuch"]

    def test_it_counts_refreshes_separately_from_reads(
        self, btc_metadata: FuturesSymbolMetadata
    ) -> None:
        fake = FakeMarketMetadataProvider([btc_metadata])

        fake.get_or_fetch("BTCUSDT")
        fake.refresh()
        fake.refresh()

        assert (fake.refreshes, len(fake.reads)) == (2, 1)

    def test_seeding_replaces_rather_than_adds(
        self, btc_metadata: FuturesSymbolMetadata
    ) -> None:
        """The real provider's `refresh()` repopulates the cache from the whole
        catalog, so a symbol the exchange delisted stops being answered. A
        fake that accumulated would keep answering it."""
        fake = FakeMarketMetadataProvider([btc_metadata])

        fake.seed([])

        assert fake.get_or_fetch("BTCUSDT") is None
