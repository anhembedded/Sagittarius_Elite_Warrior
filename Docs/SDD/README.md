# SDD — Software Design Description for `EPIC-025` Phase 0 (the module mechanism and the Walking Skeleton)

- **Status:** 🔵 Draft 2026-09-13 — round 2. The HLD says *what* and *why*; this document says
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
| SDD-03 | [`diagrams/sdd-03_contribution_render.puml`](diagrams/sdd-03_contribution_render.puml) | **Sequence diagram** — how a surface renders a place; one factory contributed to two surfaces yields two widgets sharing one trading-owned coordinator |
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
class Place(Enum):            # canonical list: Docs/VOCABULARY/README.md §2 — adding a member is an HLD change
    SCREEN = "screen"; HEADER = "header"; CONTEXT_BAR = "context_bar"; WORKSPACE = "workspace"
    RAIL = "rail"; CONSOLE = "console"; MODAL = "modal"
    SETTINGS_SECTION = "settings_section"; STATUS_TILE = "status_tile"; DEV_PROBE = "dev_probe"

class SizeHint(Enum): COMPACT = "compact"; REGULAR = "regular"; TALL = "tall"

@dataclass(frozen=True, slots=True)
class ContributionDescriptor:
    module_id: str
    surface_id: str            # "trading", "dev_board", "settings", "backtest", "welcome", …
    place: Place
    order: int                 # ascending within (surface_id, place)
    size_hint: SizeHint
    title: str                 # what the place shows as the card/section title
    factory: Callable[[IContainer], QWidget]   # the ONLY Qt-typed field; never called at contribute time
```

`ScreenContribution` is the one exception with its own fields, because navigation metadata
(`route`, `title`, `icon`, `section_key`, sequences, `is_default`) already exists in
`ScreenRegistry` and is reused unchanged.

### Registry validation — at `contribute()` time, not at render time (pluggy's rule, HLD §7.3)

1. `surface_id` must name a surface the shell declared, and `place` must be in that surface's
   `accepts`; otherwise `ContributionError` names the module, the surface and the place.
2. `(surface_id, place, order)` may not collide; two cards at the same order fail fast rather
   than rendering in dictionary order.
3. A `DEV_PROBE` contribution while `dev.mode` is false is **dropped with one log line**, not an
   error — the module is correct, the run is just not a developer run.
4. `factory` is never invoked during `contribute()`; a guard test runs every module's
   `contribute()` against a registry that raises on any factory call.

### `register()` versus `boot()` — what each may do

| | `register(context)` | `boot(context)` | `contribute(registry)` / `subscribe(bridge)` |
| :--- | :--- | :--- | :--- |
| DI | `singleton` / `bind` only | `resolve` allowed | `resolve` allowed (inside factories, later) |
| I/O, threads, network | never | start hosted services and scheduler jobs | never |
| Qt | never | never | descriptors only; widgets are built by surfaces |
| Guard | container spy fails on `resolve` | — | registry spy fails on factory call |

### The shell's boot procedure (SDD-02, in prose)

1. Read configuration once; `dev.mode` is captured for the whole run (`--dev` wins).
2. Construct `QApplication` (the Engine's proven ordering: before `App.boot()`).
3. `app.use(module)` for each entry of `MODULES`, **in the list's own topological order** — the
   list is the source of truth; the Engine's `dependencies` sort is a check, not the mechanism.
4. `DoubleClaimCheck`: for every abstract type in `container.registrations()`, at most one module
   registered it; otherwise fail before `boot()`.
5. `app.boot()`.
6. `contribute()` then `subscribe()` for each module, in list order.
7. Build `MainWindow` from `registry.screens()`; the default route is `welcome`.

### The symbol lease (SDD-04) — `ITradingSession`

```python
class ITradingSession(ABC):
    def claim_symbol(self, symbol: str, owner_id: str) -> None: ...     # raises SymbolAlreadyLeased
    def release_symbol(self, symbol: str, owner_id: str) -> None: ...   # no-op if not held by owner
    def lease_owner(self, symbol: str) -> str | None: ...
```

`IOrderSubmission.execute(intent)` refuses an intent whose `owner_id` differs from the lease
owner of its symbol (`OrderRejectionReason.SYMBOL_LEASED`). `trading` never learns what an owner
is; `strategy` claims on arm and releases on disarm; a manual order carries `owner_id="manual"`.

### `dev.mode` and restart (SDD-05)

- Gate evaluated **once**, in the shell, before `app.use()`; the `dev_board` surface is simply not
  declared when false, so its contributions fail rule 3 above (dropped) and its `screen` is never
  registered.
- The Welcome switch writes `dev.mode` through the app's config mechanism (the writable
  `user_config.json`), then shows "takes effect after restart" and a **Restart now** button that
  calls `QProcess.startDetached(sys.executable, sys.argv[1:])` and quits. No module is loaded or
  unloaded at runtime.
