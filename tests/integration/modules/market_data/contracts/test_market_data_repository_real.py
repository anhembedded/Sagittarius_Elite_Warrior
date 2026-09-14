"""The same contract, against the real SQLite repository (HLD §10.3).

Integration because the real one needs a directory of shard files; `tmp_path`
gives each test its own, and the engines are disposed on teardown so no
`ResourceWarning` reaches the gate's log scan.

A failure here that the fake's run does not show means the two implementations
disagree — which is the entire reason for running one suite twice, and exactly
the failure `BUG-026`/`BUG-027` had no way to produce.
"""

from collections.abc import Iterator

import pytest
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.database_manager import (
    DatabaseConfig,
    DatabaseManager,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.sqlalchemy_repository import (
    SQLAlchemyMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.contract_market_data_repository import (
    MarketDataRepositoryContract,
)


class TestSQLAlchemyMarketDataRepository(MarketDataRepositoryContract):
    @pytest.fixture
    def impl(self, tmp_path) -> Iterator[IMarketDataRepository]:
        manager = DatabaseManager(DatabaseConfig(db_dir=str(tmp_path)))
        yield SQLAlchemyMarketDataRepository(manager)
        # Release the SQLite file handles; without this the GC raises
        # ResourceWarning: unclosed database, which the gate's log scan fails on.
        manager.dispose_all()
