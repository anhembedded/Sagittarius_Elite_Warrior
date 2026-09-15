"""The symbol-catalog contract, run against the verified fake (HLD §10.3).

The fake's half of "both implementations run the suite". The real one's half is
`tests/integration/modules/market_data/contracts/test_symbol_catalog_real.py`,
running these same assertions against a JSON file in `tmp_path`.

Nothing is asserted here that is not in the suite: if the fake needed a test the
real one does not pass, the fake would be wrong.
"""

import pytest
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog_repository import (
    ISymbolCatalogRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.contract_symbol_catalog_repository import (
    SymbolCatalogRepositoryContract,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_symbol_catalog_repository import (
    FakeSymbolCatalogRepository,
)


class TestFakeSymbolCatalogRepository(SymbolCatalogRepositoryContract):
    @pytest.fixture
    def impl(self) -> ISymbolCatalogRepository:
        return FakeSymbolCatalogRepository()


def test_the_seed_argument_normalises_like_a_save() -> None:
    """The fake's one addition to the port: seeding a starting state in a line,
    so a consumer's test does not have to call `save_symbols` to arrange. It
    must normalise exactly as a save does, or the shortcut would let a consumer
    test against a list the real catalog could never hold."""
    catalog = FakeSymbolCatalogRepository([" ethusdt ", "BTCUSDT", "btcusdt", ""])

    assert catalog.get_symbols() == ["BTCUSDT", "ETHUSDT"]
