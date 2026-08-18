## 2026-08-16 - [HealthExtension CQRS On-Demand Query Pattern]
**Architecture:** `HealthExtension` in `sagittarius_engine` operates on the CQRS On-Demand Query model (`HealthCheckQuery`) rather than an active background timer loop.
**Learning:** It does not run a continuous 1-second polling loop by default to prevent unnecessary CPU/I/O overhead when idle. It is intended to be called on-demand before critical workflows (e.g. pre-flight checks before `RunStaticBacktestCommand` or starting live stream) or periodically polled by UI controllers/ViewModels via a dedicated `QTimer` when active monitoring is required.
**Prevention:** Do not expect extensions in `sagittarius_engine` to spawn unmanaged background loops unless explicitly declared as a `HostedService`. Always wire on-demand queries to explicit trigger points or UI timer channels.

## 2024-08-15 - [Refactor] Split GetHistoricalKlinesQueryHandler execute method
**Smell:** The `execute` method was handling both multiple symbols mapping logic with threads as well as single symbol mapping logic, leading to mixed responsibilities and high cognitive load.
**Solution:** Split out the fetching logic for multiple symbols and single symbols into explicit private helper methods `_execute_multi` and `_execute_single` while the `execute` method only handles argument parsing and routing logic.
**Learning:** For queries handling single/multi item branching logic, pull out explicit private helper methods for the branches to ensure the main method focuses on routing only.

## 2024-08-17 - Delegate TimeFrame Resolution to Domain Object
**Smell:** Redundant hardcoded timeframe parsing dictionary (`interval_minutes = {"1m": 1, ...}`) in `SyncMarketDataCommandHandler._estimate_total_klines` instead of utilizing the domain object.
**Solution:** Refactored the method to use the existing `TimeFrame.to_seconds()` method, replacing the 17-line hardcoded dictionary with a simple division, ensuring single source of truth within the Domain layer.
**Learning:** Re-evaluate domain enums and value objects for existing resolution logic before hardcoding parameter mappings in Application layer Use Cases.
