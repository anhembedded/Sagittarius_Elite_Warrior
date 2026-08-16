## 2026-08-16 - [HealthExtension CQRS On-Demand Query Pattern]
**Architecture:** `HealthExtension` in `sagittarius_engine` operates on the CQRS On-Demand Query model (`HealthCheckQuery`) rather than an active background timer loop.
**Learning:** It does not run a continuous 1-second polling loop by default to prevent unnecessary CPU/I/O overhead when idle. It is intended to be called on-demand before critical workflows (e.g. pre-flight checks before `RunStaticBacktestCommand` or starting live stream) or periodically polled by UI controllers/ViewModels via a dedicated `QTimer` when active monitoring is required.
**Prevention:** Do not expect extensions in `sagittarius_engine` to spawn unmanaged background loops unless explicitly declared as a `HostedService`. Always wire on-demand queries to explicit trigger points or UI timer channels.

## 2024-08-15 - [Refactor] Split GetHistoricalKlinesQueryHandler execute method
**Smell:** The `execute` method was handling both multiple symbols mapping logic with threads as well as single symbol mapping logic, leading to mixed responsibilities and high cognitive load.
**Solution:** Split out the fetching logic for multiple symbols and single symbols into explicit private helper methods `_execute_multi` and `_execute_single` while the `execute` method only handles argument parsing and routing logic.
**Learning:** For queries handling single/multi item branching logic, pull out explicit private helper methods for the branches to ensure the main method focuses on routing only.

## 2024-08-16 - Extract logic from dataBounds in FastCandlestickItem
**Smell:** Large method with mixed responsibilities (calculating X bounds, visible Y bounds, and global Y bounds).
**Solution:** Extracted logic into `_calculate_x_bounds`, `_calculate_visible_y_bounds`, and `_calculate_global_y_bounds` to adhere to SRP.
**Learning:** PyQtGraph hook methods like `dataBounds` are frequently called and can grow large due to multiple modes (`ax == 0` vs `ax == 1`, with or without `orthoRange`). Splitting them into distinct computation helpers improves readability and testability.
