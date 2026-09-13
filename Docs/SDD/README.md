# SDD — Software Design Description for `EPIC-025` Phase 0 (the module mechanism and the Walking Skeleton)

- **Status:** 🔵 Draft 2026-09-13 — **round 3**, revised after the independent design review
  ([`Tasks/reports/EPIC-025_design_review.md`](../../Tasks/reports/EPIC-025_design_review.md)); the
  disposition of every finding is in the ADR §7. The HLD says *what* and *why*; this document says
  *how*, at the level of classes, sequences and states, for the code Phase 0 (`EPIC-025A`) writes.
  It answers open question O1 (contribution-point schema) concretely.
- **Reading order:** HLD §3 and §4.6 first; then the diagrams below in number order.
- **Rendering:** any PlantUML renderer; the sources were syntax-checked with PlantUML 1.2026.8.

## Diagrams

| # | File | Specifies |
| :-: | :--- | :--- |
| SDD-01a | [`diagrams/sdd-01a_module_contract_shape.puml`](diagrams/sdd-01a_module_contract_shape.puml) | **Class diagram**, high view — who owns what across the Engine, `core/contracts`, the shell and the first module, and the three seams a module author touches: `IExtension`, `contribute()`, `subscribe()` |
| SDD-01b | [`diagrams/sdd-01b_module_contract_members.puml`](diagrams/sdd-01b_module_contract_members.puml) | **Class diagram**, detail — every field and signature: `BoundedContextModule`, `IContributionRegistry`, `ContributionDescriptor`, `ScreenContribution`, `Place`, `SizeHint`, and the shell's `ModuleList`, `ContributionRegistry`, `Surface`, `DoubleClaimCheck` |
| SDD-02a | [`diagrams/sdd-02a_boot_phases.puml`](diagrams/sdd-02a_boot_phases.puml) | **Sequence diagram**, high view — the seven steps of the boot procedure, and why they are in that order |
| SDD-02b | [`diagrams/sdd-02b_boot_sequence.puml`](diagrams/sdd-02b_boot_sequence.puml) | **Sequence diagram**, detail — boot call by call: config read once, `QApplication` before `boot()`, `register()` with no `resolve()`, the double-claim check, `contribute()` / `subscribe()`, the `dev.mode` gate, the first surface |
| SDD-03 | [`diagrams/sdd-03_contribution_render.puml`](diagrams/sdd-03_contribution_render.puml) | **Sequence diagram** — how a surface renders a place; one factory contributed to two surfaces yields two independent card instances (each with its own Presenter and Coordinator), sharing only the module's feed |
| SDD-04a | [`diagrams/sdd-04a_order_path.puml`](diagrams/sdd-04a_order_path.puml) | **Sequence diagram**, high view — a tick becoming an order in six messages, and the one guard on the path |
| SDD-04b | [`diagrams/sdd-04b_order_flow_sequence.puml`](diagrams/sdd-04b_order_flow_sequence.puml) | **Sequence diagram**, detail — the same path call by call across `market_data → strategy → trading → gateway → exchange → trading feed → surfaces`, and the symbol lease refusing a manual order |
| SDD-05 | [`diagrams/sdd-05_dev_mode_state.puml`](diagrams/sdd-05_dev_mode_state.puml) | **State machine diagram** — `dev.mode` read once at boot; the Welcome switch writes `user_config.json`; restart applies it (ADR D14) |
| SDD-06a | [`diagrams/sdd-06a_market_data_ports.puml`](diagrams/sdd-06a_market_data_ports.puml) | **Class diagram**, high view — the Walking Skeleton's five ports and which bounded context requires each |
| SDD-06b | [`diagrams/sdd-06b_market_data_contracts.puml`](diagrams/sdd-06b_market_data_contracts.puml) | **Class diagram**, detail — every signature, the two DTOs, the two signals, and the implementing service behind each port |

Each numbered diagram comes in two views where the subject warranted it: **`a` is the high view**
and **`b` is the detail view** of the same thing; read `a` first. SDD-03 and SDD-05 are single
diagrams because they are already at high-view density.

**Every diagram is a named UML diagram kind — class, sequence or state machine — and its title says
which**, so each symbol has a defined meaning rather than a private one. The same convention holds
for the HLD diagrams, and it is stated in full in [`../HLD/README.md`](../HLD/README.md).

The HLD-level diagrams live next to the HLD: [`../HLD/diagrams/`](../HLD/diagrams/) (context map,
inside a module, the workbench places, the Engine track).

## Design rules the diagrams encode (the text a reviewer checks the code against)

### The contribution descriptor — one shape for every place (answers O1)

```python
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:                       # core/ is Qt-free at runtime; the guard ignores TYPE_CHECKING blocks
    from PySide6.QtWidgets import QWidget
    from sagittarius_engine.extensions.pyside_mvc import QtEventBridge

class Place(Enum):            # canonical list: Docs/VOCABULARY/README.md §2 — adding a member is an HLD change
    SCREEN = "screen"; HEADER = "header"; CONTEXT_BAR = "context_bar"; WORKSPACE = "workspace"
    RAIL = "rail"; CONSOLE = "console"; MODAL = "modal"
    SETTINGS_SECTION = "settings_section"; STATUS_TILE = "status_tile"; DEV_PROBE = "dev_probe"

class SizeHint(Enum): COMPACT = "compact"; REGULAR = "regular"; TALL = "tall"

@dataclass(frozen=True, slots=True)
class ContributionDescriptor:
    contributor_id: str        # a module_id, or "shell" for the shell's own surfaces — nothing else
    surface_id: str            # "welcome", "trading", "dev_board", "settings", "backtest", "data_management"
    place: Place
    order: int                 # sort key within (surface_id, place); collisions are allowed (see rule 2)
    size_hint: SizeHint
    factory: Callable[[IContainer], QWidget]   # the ONLY Qt-typed field; never called at contribute time
    title: str | None = None   # shown by RAIL, SETTINGS_SECTION, MODAL, DEV_PROBE; ignored elsewhere
```

`ScreenContribution` is the one exception with its own fields, because navigation metadata
(`route`, `title`, `icon`, `section_key`, `section_sequence`, `item_sequence`, `location`,
`is_default`, `is_navigable`) already exists in `ScreenRegistry`'s `NavMetadata` and is reused
unchanged; its factory returns `(View, Presenter)`.

**Who may contribute.** Only a `BoundedContextModule` (through `contribute()`) and the shell
(directly, for `welcome`, `settings` and its own screens). A **support package never contributes**:
the module that needs a support widget contributes it under its own `contributor_id` — `trading`
contributes the chart card it wants on the trading workspace, `market_data` contributes the
indicator checklist it wants on Dev Board. So `contributor_id` keeps one meaning and the two-way
module-list guard stays exact.

**Lazy factories.** `factory` is a plain function defined in the module's `ui/` package whose
**body** imports the widget module; `contribute()` therefore imports no Qt widget code. Guard: after
every module's `contribute()` has run, no module under `modules/*/ui/widgets/` is present in
`sys.modules`. This keeps `PresenterManager`'s laziness (`abstract_screen_module.py:22-30`), which
the app relies on so that boot does not load every screen's dependency tree.

### Registry validation — at `contribute()` time, not at render time (pluggy's rule, HLD §7.3)

1. `surface_id` must be one of the surfaces the shell **knows** (declared for this run, or declared
   but gated off); an unknown id is a typo and raises `ContributionError` naming contributor,
   surface and place. `place` must be in the surface's `accepts`; otherwise `ContributionError`.
2. `order` is a sort key, not a uniqueness key. Rendering order is the stable sort by
   `(order, contributor_id, factory.__qualname__)`, so two independently authored modules that both
   pick `order = 10` render deterministically instead of refusing to boot. The **uniqueness key** is
   `(surface_id, place, contributor_id, factory.__qualname__)`; registering it twice raises.
3. A contribution to a surface that is **declared but gated off for this run** (`dev_board` when
   `dev.mode` is false) is **dropped with one log line**, whatever its place. That is the normal
   user run: the twelve mirrored cards, the manual-order card, the checklist and the probes are all
   dropped together, and the app boots.
4. `factory` is never invoked during `contribute()`; a guard runs every module's `contribute()`
   against a registry that raises on any factory call.
5. `contribute()` runs after `boot()`, in the module list's order, and **may `resolve()`** — so the
   list order is observable at contribute time. That is why the list, not the Engine's sort, is the
   source of truth (boot step 3).

### Ownership of a contributed card — no Coordinator in DI (ADR D12, `async-ui-action-rule` §2)

A factory returns a **card**: a `View` and its `Presenter`, built together. The Presenter constructs
and owns its Coordinators (constructor injection, as today at `trading_presenter.py:274`) and its
own `ActionOwnershipTracker`. A card contributed to two surfaces is therefore **two independent
instances** — exactly today's behaviour, where `TradingPresenter` and `DashboardPresenter` each
construct a `LiveOrderBookCoordinator`. What is shared is **truth, not objects**: the module's feed
(one `OrderFeed`, one `PositionRefreshService`, both application-level singletons) and the events
on the bus. No Coordinator, Presenter or widget is ever registered in the container. This is what
"one widget, many places" means: one *class*, many *instances*.

### Lifetime

- A surface is built **once**, on first navigation, and kept: `PresenterManager` caches the view and
  presenter per route (`presenter_manager.py:71-79`). Factories therefore run once per surface per
  process. Navigating away hides, it does not destroy.
- Module-level subscriptions (`subscribe(bridge)`) live for the process. A card's Presenter owns a
  `QtEventBridge` of its own and calls `off_all()` in `dispose()`, as `BasePresenter` does today.
- On shutdown, `MainWindow` disposes surfaces in reverse creation order; a card whose action is in
  flight records `ActionOutcome.INVALIDATED` through its tracker before its bridge is torn down.

### Threading contract for ports

The Engine's `MemoryEventBus` delivers on the **emitting thread**. `MarketTickEvent` is emitted from
the market websocket thread; `strategy`'s handler runs there; so `IOrderSubmission.execute()` and
`ITradingSession.claim_symbol()` are called **off the main thread**. The rules, per kind:

| Kind | Rule |
| :--- | :--- |
| Port implementation | **Thread-safe by contract**: guards its state with one lock (`TradingSessionState` already has `live_submission_guard()`; the lease table lives under the same lock, and claim-then-execute is one critical section). A port never touches Qt. |
| Event | Emitted on any thread; a UI consumer subscribes through `QtEventBridge`, which hops to the main thread. Application consumers must be thread-safe. |
| Widget factory | Main thread only; a factory that is called off the main thread raises. |
| Scheduler jobs / hosted services | Task-manager threads; they reach modules only through ports and events. |

### `register()` versus `boot()` — what each may do

| | `register(context)` | `boot(context)` | `contribute(registry)` / `subscribe(bridge)` |
| :--- | :--- | :--- | :--- |
| DI | `singleton` / `bind` only | `resolve` allowed | `resolve` allowed; factories resolve later |
| I/O, threads, network | never | start hosted services and scheduler jobs | never |
| Qt | never | never | descriptors only; no widget module imported (lazy factories) |
| Guard | container spy fails on `resolve` | — | registry spy fails on factory call; `sys.modules` check |

### The shell's boot procedure (SDD-02, in prose)

1. Read configuration **once**, in one `ConfigManager` shared by the GUI and headless paths (today
   there are two: `main.py:108` and `app_bootstrapper.py:178`; unifying them is a declared
   behaviour change — headless `--dev` starts working). `dev.mode` is captured for the whole run;
   `--dev` on the command line wins.
2. Construct `QApplication` (the Engine's proven ordering: before `App.boot()`).
3. `app.use(module)` for each entry of `MODULES`, **in the list's own topological order** — the
   list is the source of truth; the Engine's `dependencies` sort is a check, not the mechanism.
4. `DoubleClaimCheck`: for every abstract type in `container.registrations()`, at most one module
   registered it; otherwise fail before `boot()`.
5. `app.boot()`.
6. `contribute()` then `subscribe()` for each module, in list order; then the shell registers its
   own surfaces and, during the strangler period, wraps each remaining `AbstractScreenModule` in a
   `ScreenContribution` whose factory calls `create_view()` / `create_presenter()` lazily
   (`LegacyScreenAdapter`, deleted in Phase 4).
7. Build `MainWindow` from `registry.screens()`; the default route is `welcome`.

### Surfaces and what each accepts

| Surface | Owner | `accepts` |
| :--- | :--- | :--- |
| `welcome` | shell | `HEADER`, `WORKSPACE` |
| `trading` | shell | `HEADER`, `CONTEXT_BAR`, `WORKSPACE`, `RAIL`, `CONSOLE`, `MODAL`, `STATUS_TILE` |
| `dev_board` (gated) | shell | the same plus `DEV_PROBE`; system controls are a `HEADER` contribution at `order = 20` |
| `settings` | shell | `SETTINGS_SECTION` |
| `backtest` | `backtesting` | `RAIL`, `MODAL` (its own widgets are not contributions) |
| `data_management` | `market_data` | `RAIL`, `MODAL` |

### Writing configuration — `IConfigWriter`

`core/contracts/i_config_writer.py`: `set(key: str, value: object) -> None` and `save() -> None`.
The shell implements it as an adapter over the Engine's `ConfigManager` (today the settings
presenter downcasts with `isinstance(self.config, ConfigManager)` at `settings_presenter.py:274`;
that downcast disappears). The Welcome switch and every settings section write through this port.

### The symbol lease (SDD-04) — `ITradingSession`

```python
class ITradingSession(ABC):
    def claim_symbol(self, symbol: str, owner_id: str) -> None: ...     # raises SymbolAlreadyLeased if another owner holds it
    def release_symbol(self, symbol: str, owner_id: str) -> None: ...   # no-op if not held by owner
```

Semantics are an **exclusive lease that refuses**, not a fencing token that supersedes:
`ActionOwnershipTracker.begin_action` invalidates the previous action (`action_superseded`), and a
lease must do the opposite, or a manual order would silently revoke an armed strategy. Who holds a
lease is **not** exposed on the public port (a diagnostic query stays internal to `trading`);
`IOrderSubmission.execute(intent)` refuses an intent whose `owner_id` differs from the holder
(`OrderRejectionReason.SYMBOL_LEASED`). `strategy` claims on arm and releases on disarm; a manual
order carries `owner_id="manual"`. The lease is an **addition** to the existing rules: `arm_strategy`
still reads `ITradingSession`'s enabled state (`arm_strategy/handler.py:62`), which is a legal
`strategy → trading` dependency.

### Errors in `contracts/` — the fifth kind

A port's failure modes are part of its contract, so `contracts/errors/` is allowed and holds only
exceptions the port raises across the boundary: `core/contracts/errors.py::ContributionError`,
`trading/contracts/errors/SymbolAlreadyLeased`, and the `OrderRejectionReason` enum.

### `market_data` handles

`IMarketDataSync.sync(...) -> SyncHandle` (a frozen DTO carrying the Engine's `CancellationToken`),
`cancel(handle)`. `IMarketStream.start(symbol, timeframe, owner_id) -> StreamHandle`,
`stop(handle)`: one owner may hold **several** streams (Dev Board shows *n* charts); `owner_id` is
the namespace used by `stop_all(owner_id)` on shutdown, which is today's
`StartLiveStreamCommand.owner` semantics ("replaces the owner's previous subscriptions") made
explicit.

### `dev.mode` and restart (SDD-05)

- Gate evaluated **once**, in the shell, before `app.use()`; the `dev_board` surface is declared but
  gated off when false, so its contributions are dropped under validation rule 3 and its `screen`
  is never registered. Backtest's chart FPS overlay also follows `dev.mode`
  (`backtest_view.py:204`), so a restart changes it too — declared.
- The Welcome switch writes `dev.mode` through `IConfigWriter` (the writable `user_config.json`),
  then shows "takes effect after restart" and a **Restart now** button that calls
  `QProcess.startDetached(sys.executable, [sys.argv[0], *argv_without_dev_flags])` and quits — the
  script path is kept, and `--dev` / `--debug` are stripped when the switch turns developer mode
  off, otherwise the flag would win again on the next run. No module is loaded or unloaded at runtime.

### Measured baselines committed in Phase 0

- `tools/measure_duplicate_members.py`: the "59 duplicated names" script, defined over
  `screens/*`, `modules/*/ui/**` and `shell/surfaces/**` together, so the Phase 1 criterion cannot
  be satisfied by moving files. Its Phase 0 output is recorded in the task file.
- `tests/unit/architecture/allowlist_module_boundaries.txt`: one entry per
  `(importing_module, imported_module)` pair, no line numbers — 10 entries as found (12 imported
  symbols across 10 import statements).
