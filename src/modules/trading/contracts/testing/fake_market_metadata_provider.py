"""`FakeMarketMetadataProvider` — `IMarketMetadataProvider`'s verified fake.

In-memory, deterministic, no Qt and no network: a test seeds the catalog it
wants and reads back how many times the port was asked to leave the cache.

@par Why this exists rather than `Mock(spec=IMarketMetadataProvider)`
`EPIC-025` PR 1.3a moved this port into `modules/trading/contracts/`, which
made `tests/unit/presentation/cli/test_trade_once_cmd.py`'s mock of it a
substitution of a port that test does not own — HLD §10.3 rule 4, caught by
`test_no_foreign_port_is_mocked.py` the moment the move landed. Rule 4 lets a
module mock *its own* internals; the CLI is not this module.

The difference is not bookkeeping. A `Mock` returns whatever the test told it
to and agrees with any assertion, so it cannot notice that `get_or_fetch()`
now answers `None` for an unknown symbol instead of a placeholder — which is
exactly the promise the port's docstring makes and the one a caller shaping an
order depends on. This fake keeps that promise and `MarketMetadataProviderContract`
pins it for both implementations.
"""

from __future__ import annotations

from collections.abc import Iterable

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)


class FakeMarketMetadataProvider(IMarketMetadataProvider):
    """The catalog a test says the exchange holds, and nothing else."""

    def __init__(self, metadata: Iterable[FuturesSymbolMetadata] = ()) -> None:
        self._catalog: dict[str, FuturesSymbolMetadata] = {}
        self.seed(metadata)
        #: Every symbol `get_or_fetch()` was asked for, in order — so a test
        #: can assert the cheap path was used once rather than per candle.
        self.reads: list[str] = []
        #: How many times `refresh()` was called. Named rather than inferred
        #: from `reads`: the port's whole point is that these are two
        #: different operations with two different costs.
        self.refreshes = 0

    def seed(self, metadata: Iterable[FuturesSymbolMetadata]) -> None:
        """Replaces the catalog. Keyed the way the real provider keys it —
        by the symbol as the exchange spells it, upper case."""
        self._catalog = {item.symbol.upper(): item for item in metadata}

    def get_or_fetch(self, symbol: str) -> FuturesSymbolMetadata | None:
        self.reads.append(symbol)
        return self._catalog.get(symbol.upper())

    def refresh(self) -> None:
        self.refreshes += 1
