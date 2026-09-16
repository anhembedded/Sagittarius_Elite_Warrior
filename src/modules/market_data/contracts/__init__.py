"""Everything the rest of the app may know about market data (HLD §3.2, ADR D4).

`market_data` owns one question — *what has the market done, and what of it do
we have stored?* — and this package is the only door into it. The boundary guard
enforces that literally: `tests/unit/architecture/test_module_boundaries.py`
lets another module or the legacy tree import
`modules.market_data.contracts.*` and nothing else under `modules/market_data/`,
so the ~60 files behind this barrel are free to move, split or be rewritten
without a single edit outside the module.

**Three kinds of thing live here, and the distinction matters:**

| Kind | Members | Who implements it |
| :--- | :--- | :--- |
| **Ports** — what a consumer needs *someone* to do | **Published** (bound in `composition/port_bindings.py`): `IMarketDataSync` (PR 0.5, four screens), `IHistoricalKlines` (PR 1.1a, six call sites), `IMarketStream` (PR 1.1b, two screens), `ISymbolCatalog` and `IRangeCoverage` (PR 1.2, two call sites each), `ISymbolMetadataProvider` (`BUG-127`, one call site — the Backtest screen's sync worker). Internal to the module: `IMarketDataRepository`, `ISymbolCatalogRepository`, `IExchangeClient`, `IExchangeSessionFactory`, `ILiveStreamService`. **`ISymbolMarketMetadataCache` moved out of that internal list with `BUG-127`** and is bound in `composition/adapter_bindings.py`: the Backtest screen reads it directly on the Qt main thread, because a cache read must not be able to make a network call, and the fetching half is the provider above. It had been listed as internal while a legacy-tree consumer resolved it — which is how it came to be bound by nobody at all | the adapters in `modules/market_data/adapters/`, and `application/sync/`, `application/stream/`, `application/queries/` for the three published ports, bound in `composition/` |
| **Answers** — the shapes a query hands back | `BacktestRangeCoverage`, `DatabaseStatusSnapshot`, `RangeCoverageSnapshot`, `SymbolMarketMetadata` | nobody: they are values |
| **Events** — what this context announces (`events/`) | `MarketTickEvent`, the sync and bulk-sync events | published by the adapters and handlers |
| **Failures** — what a consumer must be able to catch by name | `ExchangeRequestCancelledError` | raised by the adapters |

**Why the events are here and not in `core/`.** An event belongs to the context
that *raises* it (`architecture-rule.md` §6): market_data is the only thing that
can say a tick arrived or a sync finished, and everyone else only listens. They
sat in `application/events/` and `domain/events/` while every context shared one
tree; they moved here in PR 0.4a, which is what made the module's imports point
one way.

**Why `SymbolMarketMetadata` is here and not in `core/vo`.** The Published
Language admits a type only once it has at least two consumers in at least two
*modules*, measured (HLD §2.4). Today it has four importers, but market_data is
the only module among them — the rest is the legacy tree. Promoting it now would
be guessing; it is published by its owner instead, which reads the same from
outside and costs one import path to change later if `trading` turns out to need
it too.

**Why the answers are published and the producers are not.** Three screens read
every field of `BacktestRangeCoverage` to tell the user *why* a date range is
unusable, so the shape crosses the edge; the two functions that compute it stay
in `application/queries/get_backtest_range_coverage/`. A consumer imports the
answer, never the arithmetic.

**Why the commands and queries are not here.** They are `application/`, and the
legacy screens still dispatch them directly through the Engine's
`ICommandDispatcher` — a transitional import recorded in the boundary
allowlist, shrink-only, not a permission. Phase 1 replaces each dispatch with a
port call and the allowlist entries leave with it. Nothing new may add one.

Nothing here imports another module, the legacy tree, or a UI toolkit; a guard
(`test_module_domain_is_qt_free.py`) pins the last of those.
"""

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.backtest_range_coverage import (
    MAX_REPORTED_MISSING_OPENS,
    BacktestRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.bulk_sync_events import (
    BulkSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.sync_events import (
    SingleSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    ExchangeRequestCancelledError,
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_session_factory import (
    IExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    DEFAULT_KLINE_LIMIT,
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_live_stream_service import (
    ILiveStreamService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    DatabaseStatusSnapshot,
    IMarketDataRepository,
    RangeCoverageSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    CancellationCheck,
    IMarketDataSync,
    MarketDataSyncRequest,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
    StreamOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_range_coverage import (
    IRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog import (
    ISymbolCatalog,
    normalised_symbols,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog_repository import (
    ISymbolCatalogRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_market_metadata_cache import (
    ISymbolMarketMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_metadata_provider import (
    ISymbolMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.symbol_market_metadata import (
    LotSizeFilter,
    MetadataVerificationStatus,
    NotionalFilter,
    OrderIntent,
    OrderIntentValidationResult,
    PriceFilter,
    SymbolMarketMetadata,
)

__all__ = [
    "DEFAULT_KLINE_LIMIT",
    "MAX_REPORTED_MISSING_OPENS",
    "BacktestRangeCoverage",
    "BulkSyncProgressEvent",
    "CancellationCheck",
    "DatabaseStatusSnapshot",
    "ExchangeRequestCancelledError",
    "IExchangeClient",
    "IExchangeSessionFactory",
    "IHistoricalKlines",
    "ILiveStreamService",
    "IMarketDataRepository",
    "IMarketDataSync",
    "IMarketStream",
    "IRangeCoverage",
    "ISymbolCatalog",
    "ISymbolCatalogRepository",
    "ISymbolMarketMetadataCache",
    "ISymbolMetadataProvider",
    "LotSizeFilter",
    "MarketDataSyncRequest",
    "MarketTickEvent",
    "MetadataVerificationStatus",
    "NotionalFilter",
    "OrderIntent",
    "OrderIntentValidationResult",
    "PriceFilter",
    "RangeCoverageSnapshot",
    "SingleSyncProgressEvent",
    "StreamOutcome",
    "SymbolMarketMetadata",
    "normalised_symbols",
]
