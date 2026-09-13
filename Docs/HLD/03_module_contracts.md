# §3 — Module contracts

- **Diagrams (component, PlantUML) — high view first, detail second:**
  [`hld-02a_module_layers.puml`](diagrams/hld-02a_module_layers.puml) — the dependency rule
  between the five directories inside a module, the forbidden `ui → adapters` edge included;
  [`hld-02b_module_internals.puml`](diagrams/hld-02b_module_internals.puml) — what each
  directory holds and what it may import from outside the module.

## 3.1 `BoundedContextModule` — built on the Engine's `IExtension` ✅/🔵

The Engine already has what a module contract needs (measured 2026-09-11,
`sagittarius_engine/interfaces/i_extension.py`): `IExtension[TContext]` with exactly three abstract
methods, `register` / `boot` / `shutdown`; a default `descriptor` that reads the **class attributes**
`dependencies`, `optional_dependencies`, `priority`, `enabled`; and an `ExtensionManager` that
topologically sorts by `dependencies`, raises `ExtensionDependencyError` when one is missing and
`ExtensionCircularDependencyError` on a cycle, and rolls back when `register()` throws. We therefore
**do not create a new `IModule`** (ADR D2): a third module concept next to `IExtension`, the Engine's
legacy `IModule` and the app's `AbstractScreenModule` would be exactly the kind of accidental
complexity this redesign is meant to remove.

```python
# src/core/contracts/bounded_context_module.py  🔵
class BoundedContextModule(IExtension[IEngineContext], ABC):
    """One bounded context = one IExtension plus two UI hooks.

    `module_id` is a PUBLIC CONTRACT: it appears in routes, in persisted ui_state, in event names
    and as the owner id of streams and actions. Renaming it is a breaking change that requires a
    state migration.
    """
    module_id: ClassVar[str]                      # "market_data" — equal to `IExtension.name`
    dependencies: ClassVar[list[str]] = []        # ONLY the module_ids whose contracts/ we import (Engine topo-sort)

    # --- provided by the Engine ---
    @abstractmethod
    def register(self, context: IEngineContext) -> None: ...
        # ONLY DI declarations (singleton/bind). NO resolve(), NO I/O, NO Qt.
    @abstractmethod
    def boot(self, context: IEngineContext) -> None: ...
        # Every module has registered → resolving is allowed; start hosted services and scheduler jobs.
    def shutdown(self, context: IEngineContext) -> None: ...

    # --- added by the application (policy, not Engine mechanism) ---
    def contribute(self, registry: IContributionRegistry) -> None: ...   # §4
    def subscribe(self, bridge: QtEventBridge) -> None: ...              # this module's own UI subscriptions
```

**Three rules**, each with a guard or a test, turn this from a formal interface into a working one:

1. **`register()` never calls `resolve()`.** Then the order in which modules are loaded cannot
   change the outcome, and the whole class of bugs "A loaded before B, so B resolved to `None`"
   disappears. Test: run `register()` against a spying container; any `resolve` call fails the test.
2. **`dependencies` lists exactly the modules whose `contracts/` this module really imports.** A
   guard compares the declaration with the actual imports found by AST; a surplus entry fails as
   surely as a missing one.
3. **A module must be constructible without Qt.** `domain/` and `application/` import no PySide6
   (guard). This is what makes criterion C4 in §1 true in practice rather than on paper.

⚠️ Measured: `StdLibContainer.singleton()` and `bind()` **overwrite silently**; there is no
`try_bind` and no `has`, only `registrations()`. The shell therefore checks, after the `register()`
pass and before `boot()`, that no abstract type was claimed by two modules, and fails fast if one was.

⚠️ Measured: `ExtensionManager.register()` **initialises immediately** every extension whose
dependencies are already initialised, and at that stage it treats `optional_dependencies` as
mandatory. Consequently we do not use `optional_dependencies`, and the shell calls `app.use()` in
**its own topological order** — the explicit list is already sorted — so that nothing depends on
that behaviour.

## 3.2 The layout inside a module — Clean Architecture, one directory per layer

```
src/modules/<module_id>/
├── module.py            # the BoundedContextModule subclass — the ONLY file in the module that imports all four layers
├── contracts/           # PUBLIC — the only surface anyone outside may import
│   ├── i_*.py           #   ports: abstract base classes named I* (architecture-rule §2.1), one file per ABC
│   ├── dto/             #   flat frozen dataclasses — no entities, no business methods
│   └── events/          #   BaseEvent subclasses — cross-module events only (§2.5)
├── domain/              # entities, private value objects, policies — imports: core/vo, the Shared Kernel (two symbols). NO PySide6
├── application/         # use cases (command/query handlers), services, feed normalisers — imports: domain, contracts (ours and others'), core
├── adapters/            # port implementations: exchange, persistence, engine adapters — imports: application, support/*
└── ui/                  # presentation: presenters, view models, coordinators, Python widget wrappers, dev_probes/
    └── dev_probes/      #   API probe widgets (§4.4) — loaded only under dev.mode
```

The dependency rule **inside** a module (the existing guard from `architecture-rule` §3, generalised
in Phase 0 to the paths `modules/*/{domain,application,adapters,ui}`): `ui → application → domain`;
`adapters → application`; and `ui` **never** imports `adapters`. Two violations exist today —
`backtest_presenter.py:43` and `settings_presenter.py:21` — and are fixed when their modules migrate.

**QML.** The `.qml` files **stay** in `src/presentation/ui/qml/<Widget>/` (ADR D6). The Python
wrapper of a module-specific widget (`*Panel`, `*VM`) moves to `modules/<id>/ui/widgets/`. Wrappers
shared by everyone (the DataTable skeleton, the kit) live in `support/ui_kit`.

**CLI.** Each module owns its own CLI commands (`modules/<id>/ui/cli/`) and contributes them through
the `cli_command` contribution point (§4); the shell assembles the parser. The `trade-once` command,
which touches market_data, strategy and trading, belongs to `strategy`: it is "run the strategy
once", and it uses the other two modules' contracts.

**Tests.** By tier, as today (ADR D7): `tests/unit/modules/<id>/…`, `tests/integration/modules/<id>/…`;
the architecture guards are the one declared exception to mirroring and live together in
`tests/unit/architecture/` (the five existing guards move there in Phase 0).

**Persistence.** A module owns its own store under `adapters/persistence/` (its own SQLite
schema namespace, its own migrations); nothing is shared between modules, and a new module with
state — a `journal`, say — adds its own store there. This is what makes such a module a local change.

## 3.3 The four kinds of thing in `contracts/` — and the kinds that must not be there

| Kind | What it is | Example | Who calls it |
| :--- | :--- | :--- | :--- |
| **Port** (an ABC named `I*`) | synchronous, typed request/response; the owning module implements it in `application/` and registers it in DI during `register()` | `IHistoricalKlines.load(symbol, timeframe, start, end) -> tuple[MarketData, ...]` | another module, via `resolve(IHistoricalKlines)` |
| **DTO** | a flat frozen snapshot; **not** an entity | `PositionSnapshot`, `RangeCoverageSnapshot` | returned from ports; carried by events |
| **Event** | a `BaseEvent`, fire-and-forget, many listeners | `OrderFilledEvent` | the bus (`IEventPublisher`); listened to through `QtEventBridge` |
| **Error** (`contracts/errors/`) | an exception a port raises across the boundary — part of the port's contract | `SymbolAlreadyLeased`, `OrderRejectionReason` | the caller of the port |
| **Widget factory** (only through a §4 contribution, never inside `contracts/`) | `Callable[[IContainer], QWidget]` | the positions table | a surface |

**Never in `contracts/`:** entities or aggregates, the Command/Query classes of internal use cases,
Coordinators, and anything that imports `adapters/` or PySide6 (the `QWidget` type in a widget
factory is the one exception).

**Why an ABC port rather than "dispatch the other module's Query class".** This is a doctrine
decision (a pattern with a name — the *module public API interface* of the modular-monolith
literature — and `architecture-rule` §2.1's demand for explicit contracts). Three reasons:
(a) it is typed, which ends the `cast(object)` on every `ICommandDispatcher.dispatch()` result;
(b) `resolve(IPort)` with no supplier registered fails fast at boot, thanks to `dependencies` plus
DI, instead of failing at runtime twenty minutes in; (c) a module's Command and Query classes become
**internal**, so they can change freely without breaking anyone. Inside a module, its own UI keeps
dispatching its own Commands and Queries through `ICommandDispatcher`, exactly as today.

**A port implementation may be the existing handler itself.** `GetHistoricalKlinesQueryHandler`
implements `IHistoricalKlines` directly (the class gains the ABC as a base and a typed method that
calls its own `execute`); no pass-through object, no extra file per port. The typed seam is kept and
zero layers are added — the alternative, a dozen one-method delegating classes, is the accidental
complexity D2 exists to avoid.

## 3.4 Each module's contracts — round 1

The selection rule: a port is public when it **has a consumer in another module** (from the
call-site table measured on 2026-09-11); otherwise it is internal, even if it is a port under
`application/ports/` today. This list is the **minimum needed for the migration**. Adding a port
means a real consumer has appeared, and the addition is recorded here in the same pull request.
The rule is about **what is public**, not about what is designed for extension: every internal
port is still an ABC with one implementation (§7.2 of `architecture-rule.md`), so making it public
later is moving one file into `contracts/` — a local change. Each module's `contracts/` package
exists from Phase 0 even where it is empty (`backtesting`), because the seam must be there before
the second consumer, not after (`architecture-rule.md` §7.2.1).

### `market_data` (Supporting — an Open Host Service)

| Contract | Kind | Measured consumers | From today's code |
| :--- | :--- | :--- | :--- |
| `IHistoricalKlines` | port | backtesting (2 coordinators), trading (chart), dev_board, CLI `trade-once` | `GetHistoricalKlinesQuery` |
| `ISymbolCatalog` | port | backtesting, the dev_board picker, the trading combo box | `ListAvailableSymbolsQuery`, `ISymbolCatalogRepository` |
| `IMarketDataSync` | port | trading (`chart_coordinator.py:145`), backtesting (`data_sync_coordinator.py:217`), dev_board | `SyncMarketDataCommand` |
| `IMarketStream` | port | trading (`chart_coordinator.py:191`), dev_board, CLI `stream` | `StartLiveStreamCommand` / `Stop…`, `ILiveStreamService`, the owner id |
| `IRangeCoverage` | port | backtesting | `GetBacktestRangeCoverageQuery` (renamed: coverage is a market_data concept; backtest merely happened to be its first caller) |
| `MarketTickEvent`, `SingleSyncProgressEvent` | event | strategy, trading, backtesting | existing |
| `RangeCoverageSnapshot`, `SyncProgress` | DTO | — | `application/ports/i_market_data_repository.py` (the DTOs move out of the port file) |
| **Internal** | | | `IMarketDataRepository`, `IExchangeClient`, bulk sync, clear/prune/repair/audit/scan, gaps, the kline inspector, `InFlightSyncGuard`, `ISymbolMarketMetadataCache` (⚠️ never registered in DI — `backtest_presenter.py:386` silently builds its own; cleaned up in Phase 3) |

### `trading` (Supporting — the Supplier of `strategy`)

| Contract | Kind | Measured consumers | From today's code |
| :--- | :--- | :--- | :--- |
| `IOrderSubmission` | port | strategy (`LiveTradingCoordinator`), CLI `trade-once` / `order-dry-run` | `PreviewOrderQuery` + `ExecuteOrderCommand` + `CancelOrderCommand` — **the only way** to send an order (proven by `EPIC-024B`) |
| `ITradingSession` | port | strategy (`claim_symbol`, see below), surfaces | `EnableTrading` / `DisableTrading` / `EmergencyStop` plus a snapshot of `TradingSessionState` |
| `IAccountSnapshot` | port | strategy (`live_strategy_factory`, `arm_strategy` — balance check) | `ITradingAccountReader` |
| `OrderFilledEvent`, `PositionChangedEvent`, `PositionClosedEvent`, `EquitySampledEvent`, `TradingSessionChangedEvent` 🔵 | event | the charting adapter, surfaces | existing (except the new one) |
| `OrderIntent`, `OrderPreview`, `PositionSnapshot`, `OpenOrderSnapshot`, `TradingSessionSnapshot`, `AccountSnapshot` | DTO | — | `LivePosition` **never leaves** the module; `PositionSnapshot` is its flat DTO |
| **Internal** | | | `ITradingClient`, `IUserDataStream`, `ITradingSessionFactory`, `IMarketMetadataProvider` (order shaping), `IFuturesSymbolMetadataCache`, `TradingLimitPolicy`, `PositionRefreshService`, `EquityCurveRecorder`, `GetExchangeConnectionStatusQuery` (the settings section and the CLI `exchange-status` are both **trading's own**) |

**A worked example: how a dependency direction resolves a cycle.** `EPIC-024B` §4.1.2 requires a
manual order to be hard-blocked while a strategy is armed on the **same symbol**. If `trading` asked
`strategy` "what is armed?", we would have `trading → strategy`; but `strategy → trading` already
exists (sending orders), so that would be a **cycle**. The resolution uses a concept that belongs to
**trading**: a *symbol lease*. `ITradingSession.claim_symbol(symbol, owner_id)` and
`release_symbol(symbol, owner_id)`; `trading` refuses manual orders on a claimed symbol **without
knowing who claimed it**; `strategy` claims on arm and releases on disarm. It is an **exclusive lease that refuses** — the opposite of
`ActionOwnershipTracker`, which *supersedes* (`action_superseded`, `ActionOutcome.INVALIDATED`):
copying that shape would let a manual order silently revoke an armed strategy. The holder is not
exposed on the public port; the lease table lives under `TradingSessionState`'s existing lock and
claim-then-execute is one critical section (the order path runs on the websocket thread — SDD,
"Threading contract"). It **adds to** the existing rules rather than replacing them: `arm_strategy`
still reads the session's enabled flag, a legal `strategy → trading` call. It also generalises: a
second automated caller (another bot, copy-trading) uses the same mechanism without a change to
`trading`.

### `strategy` (CORE — the Supplier of `backtesting`, a Customer of `trading` and `market_data`)

| Contract | Kind | Measured consumers | From today's code |
| :--- | :--- | :--- | :--- |
| `IStrategyCatalog` | port | backtesting (picker, parameter form), surfaces (the card) | `StrategyRegistry` |
| `IStrategyEngineFactory` | port | backtesting (`run_static`, `run_historical_tick`) | `StrategyEngine` + `strategy_factory` |
| `StrategyContext` | DTO/ABC (the input a strategy sees: a candle buffer plus the current position, **neutrally** expressed) | backtesting (ACL from `PaperExchange`), trading (from `LivePosition`) | `domain/strategies/strategy_context.py` — today it imports `domain/backtesting` (**wrong direction**, fixed in Phase 2/3) |
| `SignalGeneratedEvent`, `StrategyArmedEvent` 🔵, `StrategyDisarmedEvent` 🔵, `LiveOrderBlockedEvent` | event | backtesting, surfaces | existing / new |
| `StrategyDescriptor`, `ArmedStrategySnapshot`, `Signal`, `SignalAction` | DTO | — | `value_objects/{signal,signal_action}.py` |
| **Internal** | | | `LiveStrategySession`, `LiveStrategyFactory`, `LiveStrategyConfigStore`, `LiveTradingCoordinator` (tick → signal → `IOrderSubmission`), `MarketTickEventHandler` (moved from `event_handlers/market_data/` — it drives strategy, not market data), `StrategyArmingCoordinator`, the arm/disarm use cases (moved from `use_cases/trading/`), the `IndicatorScriptRegistry` consumer |

### `backtesting` (Supporting — a Customer of `market_data` and `strategy`)

| Contract | Kind | Consumers | Note |
| :--- | :--- | :--- | :--- |
| *(no public port yet)* | — | no module needs one | `RunBacktestCommand` / `StopBacktestCommand` / `BacktestState` are bound but **dispatched by nobody** → deleted in Phase 3; if a CLI `backtest` command appears, `IBacktestRunner` is added then |
| `BacktestCompletedEvent`, `BacktestFailedEvent` | **internal** event | its own screen | not in `contracts/` |
| **Internal** | | | `PaperExchange`, `_OpenPosition`, `Trade`, metrics, `out_of_sample_*` (⚠️ `out_of_sample_split.py` imports `IMarketDataRepository` — a domain-to-port leak; fix: use `IHistoricalKlines` from application), `BrokerSimulationConfig`, the fee/margin/matching policies, 11 modals, 9 coordinators |

### `support/*` (Generic)

| Package | Contracts | Consumers |
| :--- | :--- | :--- |
| `binance_gateway` | `IExchangeSessionFactory` (market), `ITradingSessionFactory` (trading), `IExchangeCredentialsProvider`, `binance_endpoints` (venue → base URL / testnet flag), `BinanceErrorTranslator` | `market_data/adapters`, `trading/adapters`, the settings section |
| `charting` | `IChartHost` (a generalisation of the existing `IBacktestChartHost` in `screens/backtest/logic/backtest_chart_host.py`), `MarkerPoint`, `RegionSpan`, `InfoField`; `ChartCard` (QtWidgets, permanently) | trading, the strategy overlay, backtesting, the indicators runner |
| `indicators` | `IIndicatorCatalog` (script list plus runner), `IIndicator` | strategy (mathematics), backtesting, the dev_board checklist |
| `ui_kit` | no ports; widgets, tokens, `ActionOwnershipTracker`, `BaseFeed`, `app_defaults`, `sync_progress_*` | every module |

### `core/` (the application's kernel policy)

`core/contracts/`: `BoundedContextModule`, `IContributionRegistry` and its descriptors (§4),
`ICommandDispatcher`, `IEventPublisher`, `IConfigReader` (three engine-adapter ports that live under
`application/ports/` today). `core/vo/`: the table in §2.4. **No** business logic, no PySide6.

## 3.5 Mapping today's code onto modules (abridged; the full mapping is in each `EPIC-025A–E` task)

| Today | Destination | Phase |
| :--- | :--- | :-: |
| `use_cases/{sync,database}`, `queries/{get_database_*, scan_all_databases, audit_database_integrity, get_historical_klines, list_available_symbols, get_backtest_range_coverage}`, `use_cases/stream/*`, `infrastructure/persistence/*` (except the futures cache), `infrastructure/binance/{client,binance_websocket_service,market_metadata_parser}.py`, `engine_adapters/live_stream_adapter.py`, `screens/data_management`, CLI `sync` / `stream` | `modules/market_data` | 0 |
| `domain/trading`, `use_cases/trading/{enable,disable,emergency_stop,execute_order,cancel_order}`, `commands/submit_order`, `queries/{preview_order,get_open_positions,get_exchange_connection_status}`, `services/{trading_session_state,position_refresh_service,equity_curve_recorder}`, `infrastructure/binance/futures_*`, `user_data_event_parser`, `order_enum_parsing`, `persistence/futures_symbol_metadata_cache`, `entities/futures_symbol_metadata`, `policies/order_quantity_rounding_policy`, `ui/common/{order_feed,equity_feed,equity_chart_adapter,order_fill_marker,market_tick_feed,live_order_book_coordinator,execute_order_block_reason}`, the `qml/{PositionsTable,OpenOrdersTable}` wrappers, the manual order card, the session card, the context bar, CLI `exchange-status` / `order-preview` / `order-dry-run` | `modules/trading` | 1 |
| `domain/strategies`, `services/{strategy_engine,strategy_registry,live_strategy_*,live_trading_coordinator}`, `use_cases/trading/{arm,disarm}_strategy`, `event_handlers/market_data/market_tick_event_handler`, `ui/common/{strategy_arming_coordinator,signal_feed,strategy_display}`, the strategy card, the last-signal card, `StrategyParamsDialog`, `StrategyOverlayCoordinator`, CLI `trade-once` | `modules/strategy` | 2 |
| `domain/backtesting`, `use_cases/backtest`, `services/backtest_range_coverage` (the coverage computation goes to market_data), `screens/backtest` (60 files), `ui/common/base_event_logger` | `modules/backtesting` | 3 |
| `infrastructure/binance/{exchange_session_factory,binance_endpoints,binance_error_translator}`, `infrastructure/credentials` | `support/binance_gateway` | 0 (market_data needs it) |
| `components/chart_card` (27 files), `screens/backtest/logic/backtest_chart_host` (the port) | `support/charting` | 4 (the `IChartHost` port is extracted in Phase 1 because trading needs it) |
| `domain/{indicators,indicator_scripts,scripting}`, `services/indicator_script_registry`, `components/indicator_scripts`, `components/strategy_params` | `support/indicators` | 4 |
| `kit/`, `qml/kit`, `qml/DataTable`, `components/{sidebar,environment_banner,market_picker}`, `ui/common/{action_ownership_tracker,app_defaults,base_feed,sync_progress_*,health_*}` | `support/ui_kit` | 4 |
| `value_objects/*` per §2.4; `application/ports/{i_command_dispatcher,i_event_publisher,i_config_reader}` | `core/` | 0 |
| `binance_bot_module.py`, `main.py::create_app`, the 5-module tuple in `app_bootstrapper.py`, `cli_parser`, `interactive_shell` | `shell/` | 0 → shrinks each phase, deleted in 4 |
| **Dead — delete** (re-measured in round 3; the first list was wrong for four of seven): only `events/{OrderSubmitted,OrderRejected}` and `qml/StatGrid` have zero references. `RunBacktestCommand` + `BacktestState` + `StopBacktestCommand` are bound and tested but **dispatched by nobody** — delete with their tests in Phase 3. **Live, do not delete:** `services/rate_limiter` (`bulk_sync_market_data/handler.py:16`, `binance/client.py` → `market_data`, Phase 0), `services/position_state_reconciler` (`futures_user_data_stream.py:6` → `trading`, Phase 1), `services/strategy_factory` (`live_strategy_session.py`, `live_strategy_factory.py` → `strategy`, Phase 2), `ui/common/system_error_feed` (imported by `order_feed.py` → `trading`, Phase 1) | — | the phase of the module that contains it |
