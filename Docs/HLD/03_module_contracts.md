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
| **Port** (an ABC named `I*`) | synchronous, typed request/response; the owning module implements it in `application/` and registers it in DI during `register()` | `IHistoricalKlines.load(symbol, interval, *, limit, start_time, end_time, newest_first) -> tuple[MarketData, ...]` | another module, via `resolve(IHistoricalKlines)` |
| **DTO** | a flat frozen snapshot; **not** an entity | `TradingSessionSnapshot`, `BacktestRangeCoverage`, `LivePosition` | returned from ports; carried by events |
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
| `IHistoricalKlines` | port | **built, PR 1.1a** — six call sites: backtesting (2 coordinators), trading (chart), dev_board (stream controller), data_management (kline inspector), CLI `trade-once` | was `GetHistoricalKlinesQuery`, whose `list | dict`-by-runtime-type return the port replaced; implemented by `StoredKlinesReader`, and the query itself was deleted once nothing dispatched it |
| `ISymbolCatalog` | port | **built, PR 1.2** — the shared symbol picker (`modules/market_data/ui/symbol_options_coordinator`, moved there with `EPIC-025E` PR 4.4a; used by backtesting, the dev_board picker and the trading combo box) and Data Management's auto-discover | was `ListAvailableSymbolsQuery`, deleted once nothing dispatched it; implemented by `SymbolCatalogService` over `ISymbolCatalogRepository` + `IExchangeClient`. `list_symbols(force_refresh=False) -> tuple[str, ...]`, normalised — **no `quote_asset`**: nothing filters by it (the picker's tabs split the list in the UI), so publishing the parameter would publish a filter nobody implements (HLD §2.4) |
| `IMarketDataSync` | port | **built, PR 0.5** — four consumers: trading (`chart_coordinator`), backtesting (`data_sync_coordinator`), dev_board (`stream_lifecycle_controller`), data_management (`sync_coordinator`) | `SyncMarketDataCommand`, wrapped by `MarketDataSyncService`; the published request is `MarketDataSyncRequest` (6 fields — `days_back_if_empty` stayed internal, no caller ever set it) |
| `IMarketStream` | port | **built, PR 1.1b** — two screens: trading (`chart_coordinator`), dev_board (`stream_lifecycle_controller`). The CLI `stream` command keeps dispatching, and the port dispatches the same two commands, so both paths stay one | `StartLiveStreamCommand` / `Stop…` wrapped by `MarketStreamService`; `start(owner_id, symbols, interval)` / `stop(owner_id)` returning `StreamOutcome`. **Not** the `StreamHandle` shape Phase 0 specified (SDD-06b now draws what shipped and records that shape in a note): a handle needs `ILiveStreamService` to hold per-stream subscriptions instead of replacing an owner's set, which is a behaviour change ADR D12 keeps out of a port PR — deferred to Phase 2, where `strategy` is the consumer that needs it |
| `IRangeCoverage` | port | **built, PR 1.2** — backtesting's chart preview and data-sync coordinators | was `GetBacktestRangeCoverageQuery`, deleted once nothing dispatched it; implemented by `RangeCoverageService`. The answer keeps the name `BacktestRangeCoverage`: the rename this row argued for waits on a second consumer *family*, measured (HLD §2.4), exactly as `SymbolMarketMetadata` waits to reach `core/vo`. `BUG-072`'s `getattr(response, "data", response)` unwrap went with the dispatch |
| `ISymbolMetadataProvider`, `ISymbolMarketMetadataCache` | port | **built, `BUG-127`** — the Backtest screen's exchange-rule check | Not in this table until `BUG-127`, and the omission is the defect. `BOT-095E1` built the rule check, the filters type and the parser; nothing bound the cache and nothing called the parser, so the screen answered *"not verified against exchange rules"* for every symbol from the day it shipped. The pair mirrors `trading`'s working `IFuturesSymbolMetadataCache` / `IMarketMetadataProvider` split: the **cache** is read on the Qt main thread and may not fetch; the **provider** fetches and is called from the screen's sync worker. Same `exchangeInfo` payload `get_available_symbols()` already fetched and discarded, so no new request weight. Verified fake + contract suite per §10.3, both implementations running it |
| `MarketTickEvent`, `SingleSyncProgressEvent` | event | strategy, trading, backtesting | existing |
| `RangeCoverageSnapshot`, `DatabaseStatusSnapshot` | DTO | — | both in `contracts/i_market_data_repository.py`, beside the internal port that answers with them — **not** `IRangeCoverage`'s answer, which is `BacktestRangeCoverage` in its own file. This row once also named a `SyncProgress` DTO: nothing by that name was ever written, and what carries sync progress across the edge is `SingleSyncProgressEvent`'s own five fields (the row above) |
| **Internal** | | | `IMarketDataRepository`, `IExchangeClient`, bulk sync, clear/prune/repair/audit/scan, gaps, the kline inspector, `InFlightSyncGuard`, `ISymbolMarketMetadataCache` (⚠️ never registered in DI — `backtest_presenter.py:386` silently builds its own; cleaned up in Phase 3) |

### `trading` (Supporting — the Supplier of `strategy`)

| Contract | Kind | Measured consumers | From today's code |
| :--- | :--- | :--- | :--- |
| `IOrderSubmission` | port | strategy (`LiveTradingCoordinator`), CLI `trade-once` / `order-dry-run` | **built, PR 1.3b** — `preview(request)` / `submit(request, live=False)` / `cancel(symbol, client_order_id)`, implemented by `OrderSubmissionService` over `PreviewOrderQuery` + `ExecuteOrderCommand` + `CancelOrderCommand`, which stay **internal**: publishing a command object is the transitional dispatch surface this epic retires. The three commands remain **the only way** to send an order (proven by `EPIC-024B`), and the port repeats none of their gates or limits — the CLI reaches the same handlers, so a rule copied here would make the two paths diverge |
| `ITradingSession` | port | strategy (`claim_symbol`, see below), surfaces | **built, PR 1.3b** — `snapshot()` / `enable()` / `disable()` / `emergency_stop()`, implemented by `TradingSessionService` over the three existing commands. `snapshot()` answers a frozen `TradingSessionSnapshot` of **three** fields — `enabled`, `orders_sent_this_session`, `known_open_symbols` — because those are the three the four presentation files were measured reading straight off the mutable `TradingSessionState` (HLD §2.4). `TradingSessionState.read_all()` takes its lock once so those three cannot be read as a combination that never existed. **`claim_symbol` / `release_symbol` since PR 2.1f**, when its first consumer arrived: `strategy` claims on arm and releases on disarm, and `ExecuteOrderCommandHandler` refuses an order whose `owner_id` is not the holder's, as a fourth `ExecuteOrderSafetyGate`. It turned out **not** to be new behaviour at all — `DashboardPresenter` had been enforcing exactly this rule since 2026-09-09, so what shipped is the same refusal moved from one screen to the order path every caller goes through. Three deviations from the design below, all measured: a `bool` rather than a `SymbolAlreadyLeased` raise, **one symbol per owner** (re-arming releases the first, since `LiveStrategySession.arm()` re-arms without disarming), and the gate read twice — cheaply ahead of `check_connection()` so a refusal stays free, then authoritatively inside `live_submission_guard()`. `Docs/SDD/05` §3 carries all of it |
| `IAccountSnapshot` | port | strategy (`live_strategy_factory`, `arm_strategy` — balance check) | **built, PR 1.3b** — `check_connection()` / `open_positions()`, implemented by `AccountSnapshotService` over the two read-only queries. Two questions, one port, because both are the same act: read the account, change nothing. Neither raises: every failure is a named `ConnectionFailureKind` inside the answer, which is what `submit()`'s first safety gate is written against with no `try`. The internal `ITradingAccountReader` it wraps keeps its name and its own verified fake (PR 1.3a) |
| `OrderFilledEvent`, `PositionChangedEvent`, `PositionClosedEvent`, `EquitySampledEvent`, `TradingSessionChangedEvent` 🔵 | event | the charting adapter, surfaces | existing (except the new one) |
| `OrderRequest`, `OrderPreview`, `Order`, `LivePosition`, `EquitySample`, `TradingSessionSnapshot`, and the four answer types (`ExecuteOrderResult`, `CancelOrderResult`, `EnableTradingResult`, `EmergencyStopResult`) | DTO | — | **Corrected by PR 1.3b, measured.** This row used to read `OrderIntent`, `PositionSnapshot`, `OpenOrderSnapshot`, `AccountSnapshot` and to say *"`LivePosition` **never leaves** the module; `PositionSnapshot` is its flat DTO"*. It does leave, under its own name, and so does `Order`: measured before deciding, `Order` is a frozen dataclass with eleven fields and **zero** methods, and `LivePosition` is frozen with eight scalar fields, a `LiquidationPrice` (a `NewType` over `Decimal`) and one pure derivation (`side`, the sign of `position_amt`). A `PositionSnapshot` would be field-for-field identical — behaviour-free churn, which is the same argument PR 1.2 used to keep the name `BacktestRangeCoverage`. `AccountSnapshot` likewise never appeared: what the account read answers with is `ExchangeConnectionStatus`, which already existed and already carried every field three consumers read. `OrderIntent` became **`OrderRequest`**, because `order_intent_for()` in `domain/policies/` already owned that name for the `(side, reduce_only)` pair a `SignalAction` maps to, and `market_data/contracts/symbol_market_metadata.py` holds a third `OrderIntent` — two published types with one name is how a reader picks the wrong one. **PR 2.1a publishes that pair as `contracts/order_intent.py`**, so this row's `OrderIntent` exists after all: measured, both producers are `domain/policies/` tables while both consumers are outside the module, and `order_intent_for()` — the `strategy` bridge this row's §02 counterpart calls *"strategy only (plus trading through the bridge)"* — has no caller inside `trading` and leaves for `modules/strategy` in Phase 2. `OrderRequest` keeps its name for the reason that justifies it rather than for the collision: a published contract does not speak the CQRS vocabulary of the module behind it |
| `TradingLimits`, `TradingLimitViolation`, `TradingLimitContext`, `TradingLimitCheck` | DTO + enum (published) | `strategy`'s `trade-once` and its formatter, the shared `execute_order_block_reason` | **Published by PR 2.1g**, and the type had crossed long before the file did: `ExecuteOrderResult` has carried a `TradingLimitViolation` in its `blocked_by` union, a `limit_checks` tuple and the `limit_context` they were judged against **since PR 1.3b**, so every consumer reading that answer imported three types out of `domain/policies/`. `TradingLimitPolicy` — the evaluator — stays internal: publishing the answer is not publishing the judgement. `ExecuteOrderResult` also gained `limits`, which is what let `trade-once` stop doing `container.resolve(TradingLimitPolicy)` to read one attribute for its display |
| `OrderQuantityRoundingPolicy`, `NotionalCheck` | domain policy (published) | `strategy`'s `position_sizing_bridge`, CLI `order_preview_formatter`, `scripts/epic021c_metadata_probe.py` | **Published by PR 2.1d**, and the measurement is the one PR 2.1a used for `OrderIntent`: what a module's `contracts/` holds is what crosses its boundary, and this already did — `contracts/order_preview.py` has a `notional_check: NotionalCheck` field, so a consumer reading that answer had to import the enum out of `domain/`. It is also the half of order construction that carries no trading decision: what the venue accepts is a filter, while whether to trade at all is `TradingLimitPolicy`, which stays internal. ADR D17 draws the same line from the other side — `strategy` sizes in capital, `trading` owns the lot and tick filters — so the rounding rule has to be reachable from `strategy` without a boundary violation, and publishing what already crossed beats a second copy of `ROUND_FLOOR` |
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
"Threading contract"). **Built in PR 2.1f**, and one sentence above needs its correction recorded
here rather than left standing: *"`trading` refuses manual orders on a claimed symbol"* is what it
does, and it does it by comparing `OrderRequest.owner_id` against the holder — so it refuses
**every** order from another owner, not only a manual one, which is the whole reason the rule left
the Dev Board's own form. `MANUAL_OWNER` is that field's default precisely so a caller which
forgets to identify itself is refused rather than waved through. It **adds to** the existing rules rather than replacing them: `arm_strategy`
still reads the session's enabled flag, a legal `strategy → trading` call. It also generalises: a
second automated caller (another bot, copy-trading) uses the same mechanism without a change to
`trading`.

### `strategy` (CORE — the Supplier of `backtesting`, a Customer of `trading` and `market_data`)

| Contract | Kind | Measured consumers | From today's code |
| :--- | :--- | :--- | :--- |
| `IStrategyCatalog` | port | backtesting (picker, parameter form), surfaces (the card) | `StrategyRegistry` — **written, measured and not shipped by PR 2.1c.** A keys-only port had no consumer it could serve alone: all four callers that read the keys also need the strategy *classes* (both Presenters and `backtest_presenter` hand `available()` to coordinators that construct one for `chart_line_colors()`; `trade_once_cmd` hands the registry to `build_engine()`), and a published contract may not carry `BaseStrategy`. The three UI callers' class-reads become intra-module in PR 2.1e and the CLI's exits with `IStrategyEngineFactory` in Phase 3, so the port is worth writing at 2.1e rather than now — `EPIC-025C` §5 carries the measurement |
| `IStrategyEngine` + `IStrategyEngineFactory` | port | backtesting (`run_static`, `run_historical_tick`) | **built, PR 3.1b.** Two ports, not one: the factory answers with an **interface**, because PR 2.1c's lesson is that a published contract may not carry a domain type and `StrategyEngine` holds an `IStrategy`, a dict of `IIndicator`s and a publisher. `IStrategyEngine` carries **two** of that class's three public methods — `run_batch()` has no caller outside the module in `src/`, so publishing it would promise what nobody asked for (PR 1.2's `quote_asset` reasoning). The asymmetry between `on_tick()` (commits) and `on_forming_bar_tick()` (peeks) is `BOT-042D`'s and is pinned by the contract suite, because a consumer that flattened it would advance indicators on bars that never closed. Implemented by `StrategyEngineFactory` over `strategy_factory`'s existing `build_engine()`; verified fake + contract suite per §10.3 |
| `ISizingPolicy` (ADR D17) | port | backtesting (paper fills), `strategy`'s own `LiveTradingCoordinator` | **Shipped, PR 2.1d.** `contracts/i_sizing_policy.py` — `allocate(...) -> MarginAllocation`, capital rather than a quantity, because turning capital into a quantity needs the symbol's lot filter and ADR D17 leaves the exchange's filters with `trading` (which is also why `OrderQuantityRoundingPolicy` is published now: see `trading`'s table). `MarginSizingPolicy` (`domain/policies/`) carries `calculate_margin_and_notional()`'s formula unchanged; `position_sizing_bridge` moved in beside it and is the one step from capital to a step-rounded quantity. Consumers measured: `PaperExchange` — its constructor takes the port — the bridge, and the two backtest handlers since **PR 3.1b**, which is also when this port gained a container **binding**. It had none until then, deliberately (a binding nothing resolves is the dead wiring `BUG-120` was), and `PaperExchange` defaulted to `MarginSizingPolicy()` imported from `domain/policies/` — the one allowlist line ADR D17 scheduled for Phase 3. The default stays, because that constructor has fifty-five inline call sites in its own test file that pass no policy (`.claude/rules/pitfalls/source.md` 1), but it now comes from `contracts/default_sizing_policy()`: the same one implementation, reached through this module's published surface instead of across the boundary, so backtest and live sizing remain one number by construction — D17's actual requirement. **No verified fake,** against §10.3 rule 1 and deliberately: the implementation is pure arithmetic with no I/O to stand in for, so a double could only re-type the formula or answer canned numbers ([`CS-001`](../CASE_STUDIES/CS-001_a_double_that_could_not_disagree.md)). `SizingPolicyContract` runs against the real one in the unit tier, and it exists for the second implementation ADR D17 promises the user (ATR-based, Kelly) |
| `StrategyContext` | DTO/ABC (the input a strategy sees: a candle buffer plus the current position, **neutrally** expressed) | **none outside this module** — measured, `EPIC-025D` §8 | `modules/strategy/domain/strategies/strategy_context.py`. This row used to read *"today it imports `domain/backtesting` (**wrong direction**, fixed in Phase 2/3)"* — the wrong direction is **gone**, and it went without anybody fixing it: PR 2.1b's move carried the file, and its imports are now `core/vo`, `trading/contracts` and `support/indicators` only. It is **not published, and now deliberately never will be** (`EPIC-025D` §8): the ACL that was to build one from `PaperExchange` state is measured out. Nothing outside this module constructs a `StrategyContext`; `backtesting` hands the engine one `PositionSide` through `IStrategyEngine.on_tick()`, which *is* the boundary. Publishing it would drag `MACDValue` and `SupportResistanceValue` into this module's contracts for a translation nobody needs |
| `SignalGeneratedEvent`, `StrategyArmedEvent` 🔵, `StrategyDisarmedEvent` 🔵, `LiveOrderBlockedEvent` | event | backtesting, surfaces | existing / new |
| `StrategyDescriptor`, `ArmedStrategySnapshot`, `Signal`, `SignalAction` | DTO | — | `Signal`, `SignalAction` and `LiveStrategyConfig` are `modules/strategy/contracts/{signal,signal_action,live_strategy_config}.py` **since PR 2.1b**, with `SignalGeneratedEvent` under `contracts/events/`; **`ArmedStrategySnapshot` arrived with `IArmedStrategy` in PR 2.1c**, and its two fields are a measurement rather than the spec's: §3.4 said "carrying `symbol`", but `LiveStrategyConfig` already carries `symbol`, while the Dev Board was reading the config **and** whether an engine is running through two separate acquisitions of the session's lock — so it carries `config` and `engine_running` and answers both in one call. `StrategyDescriptor` is still **not written**: it belongs to `IStrategyCatalog`, which PR 2.1c measured and deferred (see that port's row above), and a DTO with no port to carry it would be a seam invented ahead of its need |
| **Internal** | | | `LiveStrategySession`, `LiveStrategyFactory`, `LiveStrategyConfigStore`, `LiveTradingCoordinator` (tick → signal → `IOrderSubmission`), `MarketTickEventHandler` (**done PR 2.1c-2** — moved from `event_handlers/market_data/`, where a folder name was the only market-data thing about it: it reads one published event and drives this context's session, and `StrategyModule.boot()` owns its subscription), `StrategyArmingCoordinator`, the arm/disarm use cases (moved from `use_cases/trading/`), the `IndicatorScriptRegistry` consumer |

### `backtesting` (Supporting — a Customer of `market_data` and `strategy`)

| Contract | Kind | Consumers | Note |
| :--- | :--- | :--- | :--- |
| *(no public port yet)* | — | no module needs one | `RunBacktestCommand` / `StopBacktestCommand` / `BacktestState` were bound but **dispatched by nobody** — **deleted PR 3.1a**, re-measured first: the only non-test references were the three container registrations. The replay loop also republished historical candles as `MarketTickEvent` on the real bus, which since PR 2.1c-2 is the live strategy's own subscription, so the deletion removes a path to a real order from historical data. If a CLI `backtest` command appears, `IBacktestRunner` is added then |
| `BacktestCompletedEvent`, `BacktestFailedEvent` | event | its own screen | **in `contracts/events/` since PR 3.1c.** This row said *"internal, not in `contracts/`"*, and it was wrong on the same measurement PR 1.3b made for `trading`: a type that crosses the boundary is published whether or not anyone declared it so, and these two are read five times each from outside the context |
| `BacktestResult`, `Trade`, `BacktestMetrics`, `ExitReason`, `BacktestCancelled`, `OutOfSampleValidation` | DTO | the Backtest screen (its whole display) | **published PR 3.1c.** These are the *answers* a run hands back, and putting them in `contracts/` with the move is what turned 33 measured inbound imports into **three** allowlist entries — PR 1.3b's first half, repeated: it took `trading`'s inbound count 61 → 41 without touching a consumer |
| `CommissionType`, `Currency`, `BrokerSimulationConfig` | DTO | the Backtest screen's configuration form | **published PR 3.1c**, and they came from `src/domain/value_objects/` — the legacy tree. Measured, every consumer is this context or its screen, so they were never shared vocabulary; `core/vo` admits a type only with two consumers in two *modules* (HLD §2.4) and these have one |
| **Internal** | | | `PaperExchange`, `FillPricing`, `OpenPosition`, the three fill policies (`fee_calculator`, `margin_risk`, `order_matching`), `out_of_sample_split`'s helpers, `progress_throttle`, and **both command/handler pairs** — the runners stay internal, which is why the screen's three dispatches are allowlisted rather than legal: HLD's own answer is `IBacktestRunner`, *"if a CLI `backtest` command appears"*. `Trade` and the metrics left this row for `contracts/` in PR 3.1c (see above). PR 3.1c-2 split `paper_exchange.py` (472 lines, 72 over the ceiling) into the three things it was holding — the books, `FillPricing`'s arithmetic against the run's configuration, and the `OpenPosition` record — all three still internal |

### `support/*` (Generic)

| Package | Contracts | Consumers |
| :--- | :--- | :--- |
| `binance_gateway` | `IExchangeSessionFactory` (market), `ITradingSessionFactory` (trading), `IExchangeCredentialsProvider`, `binance_endpoints` (venue → base URL / testnet flag), `BinanceErrorTranslator` | `market_data/adapters`, `trading/adapters`, the settings section |
| `charting` | `IChartHost` (a generalisation of the existing `IBacktestChartHost` in `screens/backtest/logic/backtest_chart_host.py`), `MarkerPoint`, `RegionSpan`, `InfoField` — **`InfoField` shipped in PR 1.6f**, split out of `domain/indicator_scripts/base_indicator_script.py` and re-exported there, because it was the one thing keeping the package from being extracted; `ChartCard` (QtWidgets, permanently) — **the package arrived in PR 1.6f**: `chart_card` (27 files), `timeframe_picker` and the QML `TimeframePicker` | trading, the strategy overlay, backtesting, the indicators runner |
| `indicators` | `IIndicatorCatalog` (script list plus runner), `IIndicator` — **the package arrived in PR 1.6g**: `domain/{indicators,indicator_scripts,scripting}`, the script registry and the script-list UI, 26 files. The ports are not published yet: their consumers are Phase 2's `strategy` and Phase 3's backtesting, both still legacy. Note the shape — the mathematics is **Qt-free** (`test_module_domain_is_qt_free.py` names those three sub-packages), while `ui/` holds a `QAbstractListModel`; that asymmetry is the same one `modules/*` has | strategy (mathematics), backtesting, the dev_board checklist |
| `ui_kit` | no ports; the surface host (`WorkbenchSurface` + `build_surface`, **arrived early in PR 1.4b** — it is the one thing a legacy screen and a module's `ui/` must both be able to render, and neither may import `shell/`); `assets/` — `Palette`, `IconLoader`, the Lucide `icons/` and the boot-time asset preflight — **arrived early in PR 1.6a**, as the one leaf of the UI tree that imports nothing but itself, and the widget `kit/` (`style.py`'s roles and tokens, `controls/`, `surfaces/`, `overlays/`, the three `guards.py` checks) **in PR 1.6b**, which `assets/` leaving had turned into the next leaf; `ActionOwnershipTracker`, `BaseFeed`, `app_defaults` and the three `health_*` files **in PR 1.6c**; `constants.py` (the size tokens), `state/`, `registry/`, `sidebar/`, `symbol_picker/` and `app_log_panel.py` **in PR 1.6d**, which also retired four of the nine lines in `baseline_shell_legacy_imports.txt` — the registry's, scheduled for Phase 5, because `shell -> support/**` needs no recorded permission; `theme_bootstrap.py`, `services/`, `qml/embed` (now `embed/`, the one place a `QQuickWidget` may be built) and `environment_banner/` **in PR 1.6e**, which needed `VenueAlignment` to reach `support/binance_gateway/contracts` first — §02's own row for it, and its only imports were already from there. **`sync_progress_*` is not ui_kit's and this row used to say it was** — measured in 1.6c against `boundaries/rules.py`: `sync_progress_feed` reads `modules.market_data.contracts.events.sync_events`, and §6.1's `support/* → modules/*` prohibition has no contracts exception, so the import is `FORBIDDEN` by the rule table, not merely allowlisted. A feed that normalises *market_data's* sync events is market_data's own UI, so it belongs in `modules/market_data/ui/` — moved there with `symbol_options_coordinator` in `EPIC-025E` PR 4.4a; §3.5's row records the move | every module |

### `core/` (the application's kernel policy)

`core/contracts/`: `BoundedContextModule`, `IContributionRegistry` and its descriptors (§4),
`ICommandDispatcher`, `IEventPublisher`, `IConfigReader` (three engine-adapter ports that live under
`application/ports/` today). `core/vo/`: the table in §2.4. **No** business logic, no PySide6.

## 3.5 Mapping today's code onto modules (abridged; the full mapping is in each `EPIC-025A–E` task)

| Today | Destination | Phase |
| :--- | :--- | :-: |
| `use_cases/{sync,database}`, `queries/{get_database_*, scan_all_databases, audit_database_integrity, get_historical_klines, list_available_symbols, get_backtest_range_coverage}`, `use_cases/stream/*`, `infrastructure/persistence/*` (except the futures cache), `infrastructure/binance/{client,binance_websocket_service,market_metadata_parser}.py`, `engine_adapters/live_stream_adapter.py`, plus (measured during the move) `services/{in_flight_sync_guard,rate_limiter}`, `entities/symbol_market_metadata`, `events/market_tick_event`, `application/events/{sync,bulk_sync}_events` | `modules/market_data` | 0 — **done, PR 0.4a** |
| `screens/data_management`, CLI `sync` / `stream` — the callers, which still dispatch the module's commands directly (41 allowlist entries) | `modules/market_data` | 0 — PR 0.4b, then Phase 1 |
| `domain/trading`, `use_cases/trading/{enable,disable,emergency_stop,execute_order,cancel_order}`, `commands/submit_order`, `queries/{preview_order,get_open_positions,get_exchange_connection_status}`, `services/{trading_session_state,position_refresh_service,equity_curve_recorder}`, `infrastructure/binance/futures_*`, `user_data_event_parser`, `order_enum_parsing`, `persistence/futures_symbol_metadata_cache`, `entities/futures_symbol_metadata`, `policies/order_quantity_rounding_policy` (in `contracts/` since PR 2.1d — see this module's contract table), `ui/common/{order_feed,equity_feed,equity_chart_adapter,order_fill_marker,market_tick_feed,execute_order_block_reason}` (**done, PR 4.1a** — six of the seven; `live_order_book_coordinator` reads `components/order_book` and travels with it. The move cost **twelve** allowlist entries and retired none, which is this epic's worst ratio and the right trade on one number: the duplication metric's Phase 1 pair fell **39 → 34**, its first fall since PR 2.1e, and 4.1b/4.1c retire all twelve. It also made `trading`'s dependency on `market_data` visible — `market_tick_feed` reads the published `MarketTickEvent`, so `TradingModule.dependencies` went from `[]` to `["market_data"]`, which `test_module_declarations.py` caught within a minute), `components/order_book/` and `live_order_book_coordinator` (**done, PR 4.1b** — the two live tables, QtWidgets since PR 1.4b-2, the `qml/{PositionsTable,OpenOrdersTable}` pair they replaced deleted. The move waited on a de-duplication rather than a dependency, which was the user's call of 2026-09-16: its two table models and Data Management's two were the same class written twice, so `support/ui_kit/table_model.py`'s `RowTableModel[TRow]` was extracted first and the move then cost the duplication ratchet **nothing** — Phase 1 pair 34 → 32, total flat at 112, where the same move had cost +8 before. `EPIC-025E` §3.9), the manual order card, the session card, the context bar, CLI `exchange-status` / `order-preview` / `order-dry-run` | `modules/trading` | 1 |
| `domain/strategies`, `services/{strategy_engine,strategy_registry,live_strategy_*,live_trading_coordinator}`, `use_cases/trading/{arm,disarm}_strategy`, `event_handlers/market_data/market_tick_event_handler` (**done PR 2.1c-2** — the last coded step of Phase 2; it emptied `src/application/event_handlers/`, leaving the four backtest use cases as all that remains under `src/application/`), `domain/trading/policies/position_sizing_bridge` + the **sizing half** of `domain/backtesting/policies/margin_risk_policy` (ADR D17 — sizing is a strategy decision; **done PR 2.1d**, and only `calculate_margin_and_notional()` came, as `MarginSizingPolicy` behind `ISizingPolicy` — leverage, mark-to-market and realized PnL are a paper broker's books and stayed with `backtesting`, or Phase 3 would have had to reach back the other way for them), `ui/common/{strategy_arming_coordinator,signal_feed,strategy_display}` + `components/{strategy_params,strategy_overlay}` (**done PR 2.1e** — 11 files, plus `StrategyCardViewModel` extracted from the two live view models, which had been carrying its nineteen members each), the strategy card, the last-signal card, `StrategyParamsDialog`, `StrategyOverlayCoordinator`, CLI `trade-once` (**done PR 2.1g** — `modules/strategy/cli/`, imported by `main.py` the way `market_data`'s `sync`/`stream` have been since PR 0.4a-2; `declare_cli()` is the *interactive shell*'s registry and `trade-once` was never one of its commands) | `modules/strategy` | 2 |
| `domain/backtesting`, `use_cases/backtest` (**done, PR 3.1c** — 29 files as `contracts/`, `domain/` and `application/`, which emptied `src/application/` entirely and left `src/domain/` holding one file: `value_objects/market_type.py`, whose only production consumer is the market picker, so it travels with that component in Phase 4) | `modules/backtesting` | 3 |
| `screens/backtest` (74 files, not 60 — re-counted in `EPIC-025D` §4.1), `ui/common/base_event_logger` | `modules/backtesting/ui` | 4 — ADR D21 **deletes** the eleven QML modals rather than moving them, which is why this half could not travel with the rest |
| `services/backtest_range_coverage` — **split three ways in PR 0.4a**, because one file held three audiences: the published `BacktestRangeCoverage` DTO (three UI consumers) → `modules/market_data/contracts`, the two builders (no consumer outside the module) → `application/queries/get_backtest_range_coverage/coverage_builders.py`, the candle-grid helpers (one consumer) → `modules/market_data/domain/candle_time.py` | `modules/market_data` | 0 — **done, PR 0.4a** |
| `infrastructure/binance/binance_endpoints`, `infrastructure/credentials`, the venue enums, `ExchangeCredentials`, `ITradingSessionFactory`, `IExchangeCredentialsProvider` | `support/binance_gateway` | 0 — **done, PR 0.3** |
| `application/ports/i_exchange_session_factory` (returns `IExchangeClient`, a market-data shape) | `modules/market_data/contracts` | 0 — **done, PR 0.4a** |
| `infrastructure/binance/exchange_session_factory` — **stayed put in PR 0.4a**: one instance answers both `IExchangeSessionFactory` and trading's `ITradingSessionFactory`, and splitting a shared instance is a behaviour change, not a move. Allowlisted, one entry, with this exit | `support/binance_gateway`, split one factory per context | **1**, with `modules/trading` |
| `infrastructure/binance/binance_error_translator` (needs `OrderRejectionReason`, trading's vocabulary) | `support/binance_gateway` | **1**, with `modules/trading` |
| `components/chart_card` (27 files), `screens/backtest/logic/backtest_chart_host` (the port) | `support/charting` | 4 (the `IChartHost` port is extracted in Phase 1 because trading needs it) |
| `domain/{indicators,indicator_scripts,scripting}`, `services/indicator_script_registry`, `components/indicator_scripts`, ~~`components/strategy_params`~~ | `support/indicators` | 4 |

**Corrected by PR 2.1e — `components/strategy_params` is `modules/strategy/ui`, not this package.**
The row was unsatisfiable as written and `EPIC-025C` §3.1 recorded it as open. `bot_params_form.py`
needs `BaseStrategy`, and §6.1 forbids a support package from importing a module at all — there is
no `contracts/` exception for that direction, because a support package that knew a bounded context
existed would stop being support. The package also renders *a strategy's* parameters, which is
strategy's language and not indicator mathematics; what genuinely belongs here is the `scripting`
half it reads (`step_numeric_param_value`'s neighbours), and that stayed. So the four files moved
into `modules/strategy/ui/strategy_params/` with the rest of that context's display code, and the
Backtest screen's use of them is an allowlist entry `EPIC-025D` repays.
| `assets/` (`palette.py`, `icon_loader.py`, `asset_validator_extension.py`, `icons/`) — **done, PR 1.6a**: measured the only sub-package of `presentation/ui/` whose imports are stdlib, PySide6, the Engine and itself, so it could be lifted with no backward import and no allowlist entry, and 40 legacy consumers simply point at the new root | `support/ui_kit` | **1** |
| `kit/` (28 files) — **done, PR 1.6b**: `assets/` leaving made it the next leaf, and it is the one every other row here waits on. `page_shell.py` and `style.py` travelled with it and are still scheduled for deletion by HLD §11 / ADR D21 — a package is the unit that moves, and splitting one across two trees mid-migration is worse than carrying two doomed files | `support/ui_kit` | **1** |
| `ui/common/{action_ownership_tracker,app_defaults,base_feed,health_*}` (6 files) — **done, PR 1.6c**: all six are leaves, `ui/common` is a package this epic *dissolves* rather than moves (`EPIC-025E` step 4), and the 42 import sites were rewritten rather than left on a re-export from a package that is going away | `support/ui_kit` | **1** |
| `ui/common/sync_progress_{feed,report}`, `symbol_options_coordinator` — **re-assigned, measured in PR 1.6c, moved in PR 4.4a.** `sync_progress_feed` reads `modules.market_data.contracts.events.sync_events` and `symbol_options_coordinator` reads `modules.market_data.contracts.i_symbol_catalog`; §6.1 forbids `support/* → modules/*` outright, so `support/ui_kit` was never a legal home; a feed/coordinator normalising one module's events or catalog is that module's UI, not a generic kit. `sync_progress_report` (the DTO) travelled one step further, into `modules/market_data/contracts/`, since it crosses the module boundary as data | `modules/market_data/ui` | **4.4a** |
| `constants.py`, `state/`, `registry/`, `components/sidebar`, `components/symbol_picker`, `components/app_log_panel` — **done, PR 1.6d** | `support/ui_kit` | **1** |
| `qml/kit`, `qml/DataTable`, `components/{environment_banner,market_picker}` | `support/ui_kit` | 4, or earlier — `environment_banner` needs `VenueAlignment` to reach `support/binance_gateway/contracts` first (§02's own row for it); `market_picker` waits on `qml/SelectList`, which Phase 4 deletes, and the two `qml/*` rows are arguably not worth moving at all for the same reason |
| `value_objects/*` per §2.4; `application/ports/{i_command_dispatcher,i_event_publisher,i_config_reader,i_cqrs}` — `i_cqrs` was added to this row during PR 0.4a: with 29 importers it is the most-shared port in the app, and leaving it in the legacy tree made the first module import *backwards* | `core/` | 0 — **done, PR 0.4a** |
| `binance_bot_module.py`, `main.py::create_app`, the 5-module tuple in `app_bootstrapper.py`, `cli_parser`, `interactive_shell` | `shell/` | 0 → shrinks each phase, deleted in 4 |
| **Dead — delete** (re-measured in round 3; the first list was wrong for four of seven): only `events/{OrderSubmitted,OrderRejected}` and `qml/StatGrid` have zero references. ~~`RunBacktestCommand` + `BacktestState` + `StopBacktestCommand`~~ **deleted PR 3.1a** with their two test files, after re-measuring that nothing outside the container registrations named them. **Live, do not delete:** `services/rate_limiter` (one importer, inside `market_data` — moved in as module-internal, PR 0.4a), `services/position_state_reconciler` (`futures_user_data_stream.py:6` → `trading`, Phase 1), `services/strategy_factory` (`live_strategy_session.py`, `live_strategy_factory.py` → `strategy`, Phase 2), ~~`ui/common/system_error_feed`~~ — **deleted, and this row is why it took two epics.** Round 3 listed it as "imported by `order_feed.py`", which was never true: `order_feed.py` only *mentions* it in a docstring, and a text search cannot tell a mention from an import. Nothing constructed the feed, so `UiActionFailedEvent` and `TaskFailed` reached nobody at runtime — `BUG-126`. Its job now belongs to `shell/system_failure_log.py`, and `tests/unit/architecture/test_a_bus_subscriber_is_constructed.py` reads the **AST** so no later row can repeat the measurement error | — | the phase of the module that contains it |
