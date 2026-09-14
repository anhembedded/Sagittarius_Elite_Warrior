"""The contract suite for `IMarketDataRepository` (HLD §10.3).

Both implementations run it: `FakeMarketDataRepository` in unit,
`SQLAlchemyMarketDataRepository` over a temp directory in integration. A
subclass supplies the `impl` fixture and inherits every assertion.

**Where these guarantees came from.** Not invented — lifted from the 21
integration tests the real repository already had, which were the only written
record of its behaviour. The split was by audience, per HLD §10.3 rule 2:

| Stayed with the real implementation | Promoted here |
| :--- | :--- |
| bulk-insert chunking, shard files on disk, "a read creates no shard", SQLAlchemy's bounded streaming | everything a consumer can observe through the port |

So four tests stayed behind as SQLite concerns, and what is here is what a
backtest handler actually depends on.

**Three semantics worth reading before implementing this port**, because each
is easy to get subtly wrong and each is pinned below:

1. `get_klines()` bounds are **inclusive both ends** — `start_time == end_time`
   returns that one candle.
2. `get_range_coverage()` is the one **half-open** reader, `[start, end)`: the
   candle opening exactly at `end_time` belongs to the next range.
3. `gaps` counts **discontinuities, not missing candles**. A five-minute hole in
   one-minute data is `gaps == 1` with `DataGap.missing_candles == 4`.

**Why this file is three lines of class body.** The suite is 29 guarantees, and
one class holding them was 439 lines with 30 public methods — over both
thresholds `architecture-rule.md` §5 rule 4 calls non-negotiable, which rule 6
says apply to `tests/` and to helpers under `src/` exactly as they apply to
production code. The guarantees are grouped by the question they answer, one
file each; this file is the identity a consumer inherits, and the `impl`
fixture is the one thing every part needs and none of them can supply.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.contract_market_data_deletion import (
    MarketDataDeletionContract,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.contract_market_data_reporting import (
    MarketDataReportingContract,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.contract_market_data_storage import (
    MarketDataStorageContract,
)


class MarketDataRepositoryContract(
    MarketDataStorageContract,
    MarketDataReportingContract,
    MarketDataDeletionContract,
):
    """Inherit this and provide `impl`. Every test must pass for both."""

    @pytest.fixture
    def impl(self) -> IMarketDataRepository:
        raise NotImplementedError(
            "a MarketDataRepositoryContract subclass must provide an `impl` "
            "fixture returning the IMarketDataRepository under test"
        )
