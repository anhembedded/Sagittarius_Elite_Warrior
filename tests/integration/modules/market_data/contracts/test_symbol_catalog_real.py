"""The same contract, run against the real JSON implementation (HLD §10.3).

Integration rather than unit because the real one needs a file. `tmp_path` gives
each test its own, so these never touch the shipped
`src/config/tradeable_symbols.json`.

A failure here that the fake's run does not show means the two implementations
disagree — which is the whole point of running one suite twice, and exactly the
failure `BUG-026`/`BUG-027` had no way to produce.
"""

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.json_symbol_catalog_repository import (
    JsonSymbolCatalogRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog_repository import (
    ISymbolCatalogRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.contract_symbol_catalog import (
    SymbolCatalogContract,
)


class TestJsonSymbolCatalog(SymbolCatalogContract):
    @pytest.fixture
    def impl(self, tmp_path: Path) -> ISymbolCatalogRepository:
        return JsonSymbolCatalogRepository(tmp_path / "tradeable_symbols.json")


def test_a_missing_file_is_not_an_error(tmp_path: Path) -> None:
    """The real implementation's own concern, not the port's: the file is absent
    on a fresh install, and the contract's "empty catalog reads as an empty
    list" has to hold through that rather than through an empty file."""
    catalog = JsonSymbolCatalogRepository(tmp_path / "does_not_exist.json")

    assert catalog.get_symbols() == []
    assert not (tmp_path / "does_not_exist.json").exists()


def test_the_file_is_written_atomically(tmp_path: Path) -> None:
    """Also the real one's own: it writes a `.tmp` sibling and renames, so a
    crash mid-write cannot leave a half-written catalog that reads as corrupt.
    Asserted by checking no `.tmp` survives a completed save."""
    path = tmp_path / "tradeable_symbols.json"
    catalog = JsonSymbolCatalogRepository(path)

    catalog.save_symbols(["BTCUSDT"])

    assert path.is_file()
    assert list(tmp_path.glob("*.tmp")) == []
