# Design review — `EPIC-025` Phase 0 specification (2026-09-13)

- **Request:** an independent architectural review of the `EPIC-025` specification before the first
  line of code, judged against the author's own acceptance criteria rather than the reviewer's
  taste: *"không ngại đập đi xây lại, không ngại risk, chỉ sợ bad design, không thể mở rộng, khó bảo
  trì"* ("not afraid to tear down and rebuild, not afraid of risk; only afraid of bad design, of not
  being able to extend, of being hard to maintain"); apply named patterns and large-project
  precedent before inventing; design for extension always but build the extension only when needed;
  the application keeps running at every phase; no change in business behaviour beyond the declared
  exceptions; the Engine receives mechanism only.
- **Scope reviewed, at commit `17be6674`:**
  [`Docs/HLD/`](../../Docs/HLD/README.md) §1–§8 and its ten diagrams,
  [`Docs/SDD/`](../../Docs/SDD/README.md) and its ten diagrams,
  [the ADR](../epics/EPIC-025_module_theo_bounded_context/DECISION_2026-09-11_module_boundaries.md)
  D1–D16, [`PRO-004`](../proposal/PRO-004.md),
  [`Docs/VOCABULARY/`](../../Docs/VOCABULARY/README.md),
  [`EPIC-025`](../epics/EPIC-025_module_theo_bounded_context/README.md) and its six phase files,
  checked against `architecture-rule.md` §2.1/§5/§6/§7.2.1, `qml-rule.md` §0, `async-ui-action-rule.md`
  §1–§2 and `ONBOARDING.md` §7/§12.5.
- **Method:** every claim that depends on how the code behaves was re-measured on `src/` rather than
  assumed. Each finding below cites a file and, where the evidence is code, a line.
- **Verdict in one line:** the strategy is sound and none of the six major decisions needs
  reversing; five findings block Phase 0, and four of those five land in the first files Phase 0
  writes. A round-3 editing pass over the SDD plus four HLD sections clears them.

---

## 1. Verification basis — what re-measurement confirmed

The specification's evidence is unusually solid. Re-run on `17be6674`:

| Claim | Where | Result |
| :--- | :--- | :--- |
| 664 `.py` files, 74,371 lines | ADR §1, `PRO-004` §1 | **exact** (664 files at the ADR-date revision; 74,371 lines today) |
| `binance_bot_module.py` = 750 lines | ADR §1 | **exact** |
| `DashboardPresenter` 2,008 / `TradingPresenter` 973 | HLD §4.1 | **exact** |
| backtest screen = 12,309 lines | ADR D5, HLD §3.4 | **exact** (in 74 files, not the 60 the documents state) |
| `ui/common/` = 25 files / 2,015 lines | HLD §6.2, `PRO-004` §2 | **exact** |
| the five-screen tuple at `app_bootstrapper.py:322` | HLD §4.3 | **exact** (`ScreenRegistry()` at 322, the tuple at 323–330) |
| the CLI `if/elif` chain at `main.py:139-156` | HLD §4.3 | **exact** |
| `backtest_presenter.py:43`, `settings_presenter.py:21` | HLD §3.2, `PRO-004` §2 | **exact** |
| `backtest_presenter.py:386` builds its own metadata cache | HLD §3.4 | **exact**; `ISymbolMarketMetadataCache` appears in no `singleton`/`bind` call |
| `settings_presenter.py:143` reads `TradingSessionState` | HLD §6.4 | **exact** |
| Dev Board is the default route | HLD §4.2 | **exact** — `screens/dashboard/module.py:20`, `is_default = True` |
| the nine `ui/common` items used by exactly `{dashboard, trading}` | `PRO-004` §2 | **exact** for every item checked |
| `strategy_arming_coordinator.py` = 392 lines | `EPIC-025C` §1.1 | **exact** |
| the `LiveOrderBookCoordinator` copy-paste docstring | ADR §1, `PRO-004` §1 | **verbatim** |
| the five `application → infrastructure` constructions | HLD §7.2 | **exact** — `execute_order`, `enable_trading`, `cancel_order`, `emergency_stop`, `get_open_positions` handlers |
| the existing application guard does not catch import direction | HLD §7.2 | **correct** — `tests/unit/application/test_application_layer_structure.py` checks naming and placement only |
| **59** duplicated names | ADR §1, HLD §6.2 | **reproduced exactly** — see §7.1 for the definition and why the metric is nonetheless fragile |
| **12** boundary violations | ADR §5, HLD §7.2 | **reproduced exactly** as a per-*symbol* count — see §6.6 |

What follows are the places where the documents disagree with each other, or with the code.

---

## 2. Blockers — must change before Phase 0

### 2.1 `dev.mode = false` makes the application fail to boot

- [`Docs/SDD/README.md`](../../Docs/SDD/README.md), "Registry validation", rule 1: *"`surface_id`
  must name a surface the shell declared … otherwise `ContributionError`"*.
- Rule 3 exempts **only** `DEV_PROBE`: *"A `DEV_PROBE` contribution while `dev.mode` is false is
  dropped with one log line"*. `sdd-02b_boot_sequence.puml` repeats exactly that pairing.
- But HLD [§4.6.3](../../Docs/HLD/04_surfaces_and_contribution_points.md) rule 2 (the mirror rule)
  and `hld-03b_contribution_matrix.puml` register **twelve non-probe descriptors** against
  `surface_id = "dev_board"` — the mirrored rail cards (object `d5`), the manual-order card
  (`d2`, `RAIL`) and the indicator checklist (`d3`, `RAIL`).

In an ordinary user run the `dev_board` surface is never declared, so all twelve fail rule 1 and
raise `ContributionError` during `contribute()`. The application cannot start in the mode almost
every run uses.

**Smallest fix.** Widen rule 3 by one clause: *a contribution addressed to a surface the shell did
not declare is dropped with one log line, whatever its place*; keep the hard error for a `place`
outside a **declared** surface's `accepts`. That distinction is the useful one — a place typo is a
programming mistake, an absent surface is a configuration state.

### 2.2 SDD-03 makes a Coordinator DI-discovered, against ADR D12 and `async-ui-action-rule` §2

- ADR D12: *"Coordinators remain owned by their Presenter and injected through the constructor —
  **never DI-discovered** (`async-ui-action-rule.md` §2)"*.
- `sdd-03_contribution_render.puml`: `PP -> LOB : resolve(LiveOrderBookCoordinator) <<singleton
  owned by trading>>`, and in the dev_board block *"same coordinator; both panels update from one
  feed"*.
- [`async-ui-action-rule.md`](../../.agents/rules/async-ui-action-rule.md) §2: a Coordinator is
  *"never something that resolves its own container or is independently discoverable/DI-registered"*.
- Measured, today it is neither: `trading_presenter.py:274` and `dashboard_presenter.py:629` each
  construct their own `LiveOrderBookCoordinator(...)`, and the class appears in no `singleton` or
  `bind` call anywhere in `src/`.

So the diagram breaks a rule, breaks its own ADR, and is a **behaviour change** — two independent
instances become one shared instance — which D12 forbids. The deeper problem is §2 of this review's
§3.4: a surface has no Presenter, and `async-ui-action-rule` §1 requires that action-ownership
bookkeeping have *"exactly one owner — the Presenter (or a single shared tracker the Presenter owns
and hands to every Coordinator)"*. A container singleton shared by two live surfaces reproduces
`BOT-126`/`BUG-085` ("two screens fight over one resource") one layer up, in the subsystem that
rule was written for after five bugs.

**Smallest fix.** Name the per-surface owner. A `SurfaceSession` object that the surface constructs
once and passes into every factory satisfies §1, keeps the surface free of business logic, and lets
each widget own its coordinator exactly as today.

### 2.3 `core/contracts` cannot satisfy Phase 0's own Qt-free guard

- HLD [§6.1](../../Docs/HLD/06_enforcement_and_migration.md), `test_module_domain_is_qt_free.py`:
  no `PySide6` and no `sagittarius_engine.extensions.pyside_mvc` under `modules/*/{domain,application}`,
  **`core/**`**, `support/indicators/**` — allowlist **none**.
- HLD [§7.4](../../Docs/HLD/07_build_vs_buy.md), on the npe2 precedent: *"the one thing to copy
  deliberately is that a descriptor must be constructible with no Qt import"*.
- But `ContributionDescriptor.factory: Callable[[IContainer], QWidget]` lives in `core/contracts/`
  (SDD), and `BoundedContextModule.subscribe(self, bridge: QtEventBridge)` lives there too
  (HLD §3.1). `QtEventBridge` is `sagittarius_engine.extensions.pyside_mvc.mvc.qt_event_bridge` —
  verified at `src/presentation/ui/common/base_feed.py:54`.

The first two files Phase 0 writes fail a Phase 0 guard. HLD §3.3's *"the `QWidget` type in a widget
factory is the one exception"* is granted for a **module's** `contracts/`, not for `core/**`, whose
guard has no allowlist at all.

**Smallest fix.** Put both annotations under `if TYPE_CHECKING:` and add one clause to §6.1 saying
the guard ignores `TYPE_CHECKING` blocks. That also restores the napari property §7.4 says to copy.

### 2.4 `shell/workbench` cannot be lift-ready and build a `PageShell` at the same time

- HLD [§8.2](../../Docs/HLD/08_engine_track.md) rule 1, restated as a constraint in
  `hld-04a_engine_track_zones.puml`: the staging area (`core/contracts/`, `shell/workbench/`) may
  import *"the Engine and the standard library only"*.
- But `Surface.build(registry, container) -> PageShell` (SDD-01b; `hld-05a` draws
  `Surface *-- "1" PageShell`), and `PageShell` is application code:
  `src/presentation/ui/kit/page_shell.py:62`, whose five bands are exactly the geometry
  `VOCABULARY` §2 attributes to the places — `set_header:175`, `set_context_bar:210`,
  `set_workspace:221`, `set_console:278`, with `kit/overlay.py` for `MODAL`.
- [`EPIC-025E`](../epics/EPIC-025_module_theo_bounded_context/incomplete/EPIC-025E_phase4_support_and_dissolve_common.md)
  item 3 moves `PageShell` into `support/ui_kit` — in **Phase 4**, three phases after `Surface` is
  written.

Lift criterion 1 is therefore unsatisfiable for the one element (`Surface`) that step E2 exists to
lift. The same contradiction appears from the other side: `hld-01a_layer_map.puml` draws only
`support ..> core.vo`, with no `support → core.contracts` edge, yet `charting`, `indicators` and
`ui_kit` all construct `ContributionDescriptor`s in `hld-03b` (objects `t6`, `t13`, `d3`).

**Smallest fix.** Define an `IPlaceHost` ABC in `core/contracts/` (`slot(place) -> Container`), have
`PageShell` implement it from `ui_kit`, and add the `support → core.contracts` edge to `hld-01a`
and to the §6.1 rule text. The staging area then depends on an ABC it owns, not on app code.

### 2.5 Support packages and the shell contribute UI, but only modules have `contribute()`

`hld-03b_contribution_matrix.puml` uses `module_id = "ui_kit"` (`t13`, the log console),
`"charting"` (`t6`, the chart card), `"indicators"` (`d3`, the checklist) and `"shell"` (`w1`, the
Welcome screen). Against that:

- [`VOCABULARY`](../../Docs/VOCABULARY/README.md) §1: *"**Module** … Exactly four exist"*, and a
  support package is precisely the thing a module must not be confused with.
- HLD §3.1: only `BoundedContextModule` has `contribute()`. HLD §6.1 guard (a): *"every package
  under `modules/` appears in `shell/modules.py` and vice versa"* — `support/` is not in that list,
  so nothing ever calls a support package's hook, because it has none.
- `VOCABULARY` §1 defines `module_id` as the name used *"in routes, in persisted ui_state, in event
  names and as the owner id of streams and actions"*. `"ui_kit"` is none of those.

There is no mechanism that puts a support-package widget onto a surface, and `module_id` carries
two meanings in one field.

**Smallest fix.** State the rule: a support package never contributes; the module that wants the
widget contributes it (`trading` contributes the chart card it needs), and the shell registers its
own surfaces' widgets directly rather than through a pseudo-module id.

---

## 3. The six riskiest decisions

### 3.1 Four bounded contexts with `strategy` as the Core domain — **ACCEPT**

The cut rests on the strongest evidence a boundary argument can have: the code already keeps two
types for one word, before anyone named the boundary — `domain/trading/live_position.py`
(*"this app never computes any of its fields"*) against `_OpenPosition` in `paper_exchange.py`,
mutated by the app on every tick. C1–C6 with a measured verdict per candidate is a far better
instrument than taste, and the anti-criteria in §1.3 are what stop the next argument from being
re-litigated.

The strongest argument against is the **Core** label rather than the cut. `strategy` passes C2
thinly: its owned state is `LiveStrategyConfig` plus a `LiveStrategySession` that holds exactly one
`_config`/`_engine`/`_coordinator` under one lock (`live_strategy_session.py:67-80`); most of its
mass is coordination over `market_data` and `trading` ports. The complexity and defect mass sit in
`trading` (the `TradingSessionState` web, `BUG-111` → `BUG-117`) and `backtesting` (12,309 lines).
§2.2 already says Distillation is about where design effort goes, but a reader will hear "Core" as
"largest and hardest" and under-invest in `trading` — the phase that can lose real money on Testnet.

**Change:** one sentence in §2.2 — *Core names the reason the application exists, not the largest
module; `trading` carries the highest operational risk and receives the same review budget.*

### 3.2 ABC ports as the cross-module contract, Command/Query internal — **ACCEPT WITH CHANGE**

The three reasons in §3.3 are correct, and ending the `cast(object)` on every dispatch result is a
real, measurable gain. The pattern is named (the modular-monolith *module public API interface*),
and `architecture-rule` §2.1 demands explicit contracts rather than duck typing, so this is applying
rather than inventing.

The strongest argument against is that the application ends up with **two invocation mechanisms
permanently** — ports across modules, `ICommandDispatcher` within them — and that most port
implementations will be pass-throughs: `IHistoricalKlines.load(...)` wrapping
`GetHistoricalKlinesQuery`, `IMarketDataSync.sync(...)` wrapping `SyncMarketDataCommand`, and so on
for roughly a dozen ports, each with a file, a registration and a test. That is accidental
complexity of exactly the kind D2 was written to avoid, and all of it lands in Phase 0.

**Change:** say in §3.3 that a port implementation *may be the existing handler itself*, adapted —
the handler class implements the ABC — rather than a new object that dispatches to it. The typed
seam survives and no layer is added.

### 3.3 The symbol lease to break the trading ↔ strategy cycle — **ACCEPT WITH CHANGE**

This is the most elegant decision in the specification. A concept that genuinely belongs to
`trading` (a resource is claimed) expresses a rule about `strategy` without naming it, and it
generalises to a second automated caller at no cost. Keep it. Four things need fixing first.

1. **The cited precedent has inverted semantics.** §3.4 says the lease *"has the same shape as the
   existing `ActionOwnershipTracker`"*. It does not: `action_ownership_tracker.py:71-93` **supersedes**
   — a second `begin_action` traces `action_superseded` and finishes the incumbent as
   `INVALIDATED`. A lease must **refuse** (`SymbolAlreadyLeased`). An implementer told "same shape
   as X" will copy latest-wins, and a manual order will silently revoke a strategy's lease.
2. **`lease_owner(symbol) -> str | None` contradicts its own paragraph.** §3.4 promises *"`trading`
   refuses manual orders on a claimed symbol **without knowing who claimed it**"*, and the SDD then
   publishes the owner id back out through the port. Keep the accessor internal for diagnostics.
3. **No threading contract.** The lease lives on `ITradingSession`, hence inside
   `TradingSessionState`, which is written from the user-data websocket thread
   (`futures_user_data_stream.py:65`) and is the highest-risk mutable object in the application
   (§6.4 of this review). See §5.1.
4. **It is an addition, not a replacement.** `EPIC-025C` §1.3 says *"the symbol lease replaces the
   old hard block"*, but `arm_strategy/handler.py:62` still reads `self._session_state.enabled`.
   That is directionally legal (`strategy → trading`) and should simply be stated as such.

### 3.4 Zero-logic surfaces, a fixed place vocabulary, one descriptor shape — **ACCEPT WITH CHANGE**

"The shell owns a small fixed vocabulary of places; a module chooses a place, it never invents
layout" is the right model and has three independent precedents (VS Code, Spyder, napari). One
descriptor shape is the correct answer to ❓ O1 — a schema per kind is what makes plugin hosts
unmaintainable, and §4.6.5 reaches that conclusion for the right reason.

The strongest argument against is not the vocabulary but the word **zero**. `async-ui-action-rule`
§1 requires one owner for action bookkeeping, and removing the Presenter removes the owner; the
specification's answer is a container singleton shared across two live surfaces (§2.2 above).
Secondary: `order` is a single global integer namespace shared by independently authored modules
**with fail-fast on collision**, so adding a module can refuse to boot the application —
`hld-03b` already hard-codes 10/20/30/40/50/60/70/80 across four different owners. And `title` is
mandatory on the descriptor while being meaningless for `CONTEXT_BAR`, `WORKSPACE` and
`STATUS_TILE`.

**Change:** name the per-surface owner (§2.2); make `order` collision-tolerant by sorting on
`(order, module_id)`, or scope it per module as VS Code does with `group@order`; make `title`
optional.

### 3.5 Migration order: Walking Skeleton with `market_data` first, `trading` second — **ACCEPT**

The reasoning is sound — `market_data` really is the thinnest context that touches persistence,
REST, websocket, one screen and the CLI — and the hard constraint that the application runs at every
phase is the right one for a user who tests on Testnet daily. The Strangler Fig framing is applied,
not invented.

The strongest argument against: as scoped, Phase 0 does not actually *walk*. With one module,
`dependencies` is `[]` (`sdd-01b`), the topological sort has nothing to sort, `DoubleClaimCheck` has
one claimant, and **no cross-module port call happens anywhere**. The mechanism the skeleton exists
to prove is exercised with N = 1, and its first real test is Phase 1 — which is also the
highest-risk phase, and the wrong place to discover that the registry or the boot ordering is wrong.

**Change (small):** in Phase 0, additionally move **one existing consumer** onto a `market_data`
port — `chart_coordinator.py:145` (`IMarketDataSync`) or `data_sync_coordinator.py:217` — leaving it
in the legacy tree. One call site, and the skeleton then crosses a real boundary.

### 3.6 The Engine track as a harvested framework with a written lift criterion — **ACCEPT WITH CHANGE**

Harvest-over-design-first is correct, it is a named pattern (Fowler, 2003), and quoting `EPIC-001D`
against itself — *"choosing these abstractions early means choosing them with the least
information"* — is the right kind of argument. Keep the shape.

The criterion is the problem.

- Criterion 1 is unsatisfiable as written (§2.4).
- Criterion 2, *"used by ≥ 2 surfaces or ≥ 2 modules"*, is satisfied **trivially and immediately**
  for everything, because §4.6.3 rule 2 makes every `trading.rail` card a `dev_board.rail` card by
  default. "Two surfaces" is evidence that the mirror rule exists, not that the API is general.
- Criterion 3, *"API unchanged for one whole phase"*, has no measurement procedure.

**Change:** drop "≥ 2 surfaces" and keep "≥ 2 modules"; restate criterion 1 as *imports nothing
outside the Engine, the standard library and the named `core/contracts` ABCs*; define criterion 3 as
*no change to the signatures enumerated in the lifting task's API table*.

---

## 4. Extensibility audit (`architecture-rule` §7.2.1)

| Case | Local? | Seam, or the files that would change |
| :--- | :--- | :--- |
| Second exchange venue | ❌ **no** | §4.1 |
| Second automated order source (copy-trading) | ✅ **yes** | the symbol lease + `IOrderSubmission(owner_id)`; one package, one line in `shell/modules.py` |
| A `journal` module with its own screen | ✅ **yes**, with a caveat | §4.2 |
| Per-module QML directory | ❌ no — deliberately, with a named seam | ADR D6 + `create_quick_widget(import_paths=)`; an honest "not yet" |
| A real login replacing Welcome's **Start** | ⚠️ the button yes, identity no | §4.3 |
| Two strategies on two symbols at once | ❌ **no** | §4.4 |

### 4.1 Second exchange venue — not local, and `core/vo` makes it worse

§7.6 states that when a second venue arrives *"ccxt slots in behind the same three ports without
touching a module"*. That is true of the **ports** and false of the **vocabulary**. §2.4 promotes
`MarketDataVenue` and `TradingVenue` into `core/vo`, and both are Binance-specific closed enums:
`MarketDataVenue = {MAINNET_PUBLIC, FUTURES_TESTNET}`
(`src/domain/value_objects/market_data_venue.py`) and `TradingVenue = {DISABLED, FUTURES_TESTNET}`,
whose docstring says adding a member is deliberately a reviewed change. Adding a second venue
therefore edits the Published Language — the one package `VOCABULARY` calls *"neutral with respect
to any business language, owned by none"* — plus `binance_endpoints` (venue → base URL), both
`adapters/binance/` packages, both settings sections, and the guard test *only the session factory
constructs binance client*.

**Smallest fix:** take §2.4's own alternative. That table already offers
`support/binance_gateway/contracts` as a home for `ExchangeCredentials`/`VenueAlignment`; put the
venue types there too and leave `core/vo` with a venue-agnostic identifier. One row changes, and the
case becomes local.

### 4.2 A `journal` module — local; the persistence answer is on the wrong document

The screen, the rail card and the events it needs (`OrderFilledEvent`, `PositionClosedEvent`) are
already public in `trading/contracts`, so the UI side is genuinely one package plus one line.
Persistence is answered too — `EPIC-025` README §4 says the SQLite store stays shared and *"each
module owns a schema namespace"* — but that answer lives on the epic board, while HLD §3.2, which
describes a module's internal layout and is the north star, does not mention storage at all. Move
the sentence into §3.2.

### 4.3 A real login — the button is local, the identity is not

D13's single `StartRequested` intent is exactly the right seam and should not change. But a real
login implies a **profile**, and `user_config.json` (`app_bootstrapper.py:132,180`) and the persisted
`ui_state` are process-global, single-user artefacts; credentials live in `secrets.local.json`
behind `support/binance_gateway`. Replacing the button is one file; scoping configuration to an
identity is not, and no seam exists for it. One line in D13 saying profile-scoped configuration is
explicitly out of scope keeps the promise honest.

### 4.4 Two strategies on two symbols — not local; fix the seam in Phase 2

`LiveStrategySession` holds a single `_config`/`_engine`/`_coordinator` under one `_lock` with one
`_generation` (`live_strategy_session.py:67-80`). Supporting two would touch
`live_strategy_session.py`, `live_strategy_factory.py`, `strategy_arming_coordinator.py` (392
lines), both arm/disarm handlers, the strategy card and last-signal card view models, and
`StrategyArmedEvent`/`ArmedStrategySnapshot`, which carry no key. By §7.2.1 step 2 that is a
**closed** design, and §7.2.1 says to open it now, while it is cheap. The symbol lease is already
keyed by symbol; the session is the only thing that is not.

**Smallest fix (a seam, not a variant):** in Phase 2, key `LiveStrategySession` internally by symbol
even while only one entry can exist, and put `symbol` on `ArmedStrategySnapshot`,
`StrategyArmedEvent` and `StrategyDisarmedEvent` from the first day. One dictionary and one field.

---

## 5. Gaps a Phase 0 implementer is blocked on

1. **The threading contract for ports — the largest gap.** `sdd-04b` draws the order path as
   `market_data (websocket) → bus → strategy handler → IOrderSubmission.execute(...)`. The Engine's
   `MemoryEventBus` is synchronous on the caller's thread (HLD §5.1), so `execute()` runs on the
   **websocket thread**, while `QtEventBridge` hops the UI side to the main thread. Nothing states
   whether a port is thread-safe, main-thread-only, or free-threaded. `claim_symbol` /
   `release_symbol` mutate state that `futures_user_data_stream.py` also writes. `market_data`'s
   `IMarketStream` has the same exposure, so the rule is needed in Phase 0, not Phase 2.
2. **Which method writes `dev.mode`.** D14 says the toggle *"writes `dev.mode` to the writable
   `user_config.json` (the app's existing config mechanism)"*. That mechanism is
   `ConfigManager.save()`, which is **not** part of `IConfig`: `settings_presenter.py:274` reaches
   it through `isinstance(self.config, ConfigManager)`, and the docstring at `:112` explains why.
   `core/contracts` is specified to hold `IConfigReader` — read-only. The Welcome surface therefore
   has no port to write through, and a shell surface downcasting to a concrete Engine class is what
   §3.3 exists to prevent. A method signature is needed.
3. **Widget and subscription lifetime.** `for_place()` runs when a surface builds. `PresenterManager`
   is a lazy router — does navigating away destroy the surface and re-run every factory on return?
   `subscribe(bridge)` is called once per module at boot, but the widgets it feeds are per-surface:
   who calls `QtEventBridge.off_all()`, and what happens to an in-flight action when its widget is
   torn down? `sdd-05`'s "no hot reload" answers the module question, not the widget question.
4. **The Phase 0 bridge for legacy screens.** `EPIC-025A` §1.5 removes the five-module tuple and says
   *"the shell takes them from `screen` contributions"*, but in Phase 0 four of those five are still
   `AbstractScreenModule`s under `screens/`, not modules. Nothing states how an
   `AbstractScreenModule` enters `IContributionRegistry`, nor whether
   `ScreenContribution.factory -> (View, Presenter)` must preserve that class's lazy-import
   discipline (see 5).
5. **Lazy imports inside `contribute()`.** `abstract_screen_module.py:22-30` mandates lazy imports
   *inside* `create_view()`/`create_presenter()` so that *"registering every module at boot does not
   pull in every screen's dependency tree"*, `PresenterManager` being *"a true lazy router"*.
   `module.contribute()` runs for every module at boot and will reference roughly fifteen widget
   factories by Phase 1. If those are module-level imports, the whole Qt widget tree loads at
   startup and that property is lost. The SDD says the factory is never *invoked* at contribute
   time; it must also say it is never *imported* at contribute time.
6. **The allowlist's unit.** See §6.6.
7. **No guard rule for the legacy tree.** §6.1 defines rules for `modules/**`, `core/**`,
   `support/*` and `shell/**`, and says nothing about `src/{domain,application,infrastructure,presentation}`,
   which exist through Phase 4 and hold most of the code. During the strangler period, may legacy
   `presentation/` import `modules/market_data/contracts`? May it import that module's
   `application/`? This is the question Phase 0 meets on its first day.
8. **`SyncHandle` and cancellation.** `sdd-06b` gives `IMarketDataSync.sync(...) -> SyncHandle` and
   `cancel(handle)`. `SyncHandle` appears in no DTO table (§3.4 lists only `RangeCoverageSnapshot`
   and `SyncProgress`), and cancellation depends on `ScheduledJob.cancel()`, which the Engine does
   not have (§5.1, scheduled as E0).
9. **`IMarketStream` multiplicity.** The port is `start(symbol, timeframe, owner_id)` /
   `stop(owner_id)`, but today `StartLiveStreamCommand` *"replaces `owner`'s previous subscriptions"*
   (`use_cases/stream/start_live_stream/command.py:9-11`), so one owner holds exactly one
   subscription. Dev Board shows *n* charts. Either the signature needs a per-stream handle, or the
   contract must say Dev Board uses *n* owner ids.
10. **Where exceptions live.** `ContributionError`, `SymbolAlreadyLeased` and
    `OrderRejectionReason.SYMBOL_LEASED` all cross a module boundary, and §3.3 enumerates exactly
    four permitted kinds in `contracts/` — port, DTO, event, widget factory. An exception is none of
    them.
11. **`accepts` for shell surfaces.** Only `backtest` has a declared `accepts` (`{RAIL, MODAL}`).
    Validation rule 1 checks `place ∈ surface.accepts`, so every surface needs one; `welcome`'s is
    undefined, because §4.2 lists its "slots" as *app name · environment banner · Start · toggle*,
    none of which is a `Place`.

---

## 6. Consistency findings below blocker level

### 6.1 "Owner id" names three different mechanisms — MAJOR

`VOCABULARY` §1 defines **Owner id** as *"the string that names who holds a leased resource (a
symbol, a market stream, a background action)"*, and `sdd-06b` notes *"owner_id: the same lease idea
as trading's symbol lease"*. Measured, the three differ in the property that matters:

| Mechanism | Semantics | Evidence |
| :--- | :--- | :--- |
| `ActionOwnershipTracker` | **supersede** — a second claim invalidates the first | `action_ownership_tracker.py:71-93` |
| `StartLiveStreamCommand.owner` | **namespace** — *"replaces `owner`'s previous subscriptions … never affects another owner's"*; two owners may stream the same symbol | `use_cases/stream/start_live_stream/command.py:9-14` |
| `ITradingSession.claim_symbol` | **exclusive lease** — refuses a second claimer | `Docs/SDD/README.md` |

Three rows in `VOCABULARY` §1 (*fencing token* / *stream owner* / *symbol lease*), and deleting the
`ActionOwnershipTracker` comparison from §3.4, fixes both this and §3.3 item 1.

### 6.2 `system_controls` is a slot in the text and not a `Place` — MAJOR

HLD §4.2 lists the dev_board slots as `header · system_controls · workspace · rail · probes ·
console`, and §4.6.1 fixes the vocabulary at `SCREEN, HEADER, CONTEXT_BAR, WORKSPACE, RAIL, CONSOLE,
MODAL, SETTINGS_SECTION, STATUS_TILE, DEV_PROBE`. The new `hld-03b` resolves it — `systemControls`
becomes `place = HEADER, order = 20` — and `hld-05a` no longer draws a `system_controls` band, but
the §4.2 and §4.6 text was not updated. The same drift affects `probes` (the place is `DEV_PROBE`),
`sections` (the place is `SETTINGS_SECTION`), and `welcome`, whose §4.2 "slots" are not places at
all while `sdd-02b` calls `for_place("welcome", HEADER | WORKSPACE | ...)`.

### 6.3 The descriptor's uniqueness key is stated two ways — MAJOR

`Docs/SDD/README.md` rule 2 says *"`(surface_id, place, order)` may not collide"*; `sdd-02b` says
*"reject duplicate (surface, place, factory)"*. Different rules, different failure modes; see §3.4
for why the first is dangerous across independently authored modules.

### 6.4 `TradingSessionState`'s fan-out is understated — MAJOR

HLD §6.4 rates the risk 🔴 and describes it as *"3 Presenters, 3 handlers and the websocket thread"*.
Measured: three Presenters **plus `trading_view_model.py`**; **seven** handlers (`execute_order`,
`enable_trading`, `disable_trading`, `cancel_order`, `emergency_stop`, `arm_strategy`,
`disarm_strategy`); four services (`position_refresh_service`, `equity_curve_recorder`,
`live_strategy_session`, `position_state_reconciler`); the websocket thread; and
`binance_bot_module.py`. The 🔴 rating is right; the scope estimate behind it is roughly half the
real fan-out, which matters for Phase 1's sizing.

### 6.5 `backtesting` contributes to the `trading` surface, against §4.6.4 — MAJOR

`hld-03b` object `t4` places `backtestProgress` (`module_id = "backtesting"`) inside
`package "surface_id = trading"`, while §4.6.4's own check table records `backtesting` → *"Q2 trading
cards: ❌"*. It also makes the `trading` surface's header depend on `backtesting` being loaded.

### 6.6 The boundary allowlist has no defined unit — MAJOR

ADR §5 says *"the twelve violations the trial run found are the Phase 0 allowlist"*. Measured, the
same set of violations is **12 imported symbols**, **10 import statements**, **10 files** — of which
**2** are under `screens/`, matching §6.2's row "Screens importing `infrastructure/`: 2". §7.2's
*"the other seven are `presentation → infrastructure`"* is correct at symbol granularity (5 + 7 =
12). A hand-written AST guard naturally records `(importing module, imported module)` pairs, which
gives 10. Because the ratchet fails when the list **grows**, the unit must be fixed before the guard
is written, or the first run disagrees with the ADR by two.

Related, and worth settling in the same edit: the allowlist entry format. ArchUnit's
`FreezingArchRule` — the closest precedent — stores each violation with a **line-independent**
identity precisely so that unrelated edits do not churn the baseline. If entries carry line numbers,
every refactor in a listed file breaks the guard; if they carry only a file name, two violations in
one file collapse into one entry and the ratchet loses resolution. `(importing module, imported
module)` with no line number is the shape that works.

### 6.7 `--dev` survives the restart, and the relaunch drops the script path — MAJOR

Two concrete defects in D14 / `sdd-05`:

- `resolve_dev_verbosity(sys.argv, …)` sets `ConfigKeys.DEV_MODE = True` when `--dev` is present
  (`app_bootstrapper.py:186-193`), and both D14 and the SDD state that *"`--dev` wins for that run"*.
  The specified restart, `QProcess.startDetached(sys.executable, sys.argv[1:])`, re-passes `--dev`,
  so a user who launched with `--dev` and then switches Developer mode **off** restarts into dev
  mode again. `sdd-05`'s transition `RestartPending_D --> [*] : new process boots → UserMode` is
  false in that case.
- `sys.argv[1:]` drops `sys.argv[0]`, the script path: the relaunch is `python --dev`, not
  `python src/main.py --dev`.

The restart must pass the script path and strip `--dev` when the toggle turns dev mode off.

### 6.8 Configuration is read twice today — MAJOR

`sdd-02b` step 1 specifies *"read configuration once; `dev.mode` is captured for the whole run"*.
Today two independent `ConfigManager`s are built: `main.py:107-118`, which also loads
`cli_commands.json`, and `app_bootstrapper.py:177-180`, which applies `--dev`. Consequently `--dev`
currently reaches the GUI path only. Unifying them is right, but it is a change in user-visible
behaviour (headless `--dev` starts working) and is not among the two exceptions declared in §4.2 and
§6.3. Declare it.

### 6.9 Minor

- `hld-03a`'s `ScreenContribution` omits `is_default` and `sequences`; `Docs/SDD/README.md` lists
  both, and `hld-03b`'s `w1` sets `is_default = true`.
- `hld-03b`'s trading package holds **13** instances while object `d5` says *"the twelve instances
  above"* without naming the exclusion; `hld-05b` draws ten `same factory` links and omits
  `backtestProgress` from the trading surface entirely.
- `EPIC-025B` §1.2 names the events `OrderFilled`, `PositionChanged`, `TradingSessionChanged`, and
  `EPIC-025C` §1.2 names `SignalEmitted`. The code has `order_filled_event.py`,
  `position_changed_event.py`, `signal_generated_event.py`, and the HLD uses the `*Event` names.
  D12 forbids renames inside a pure refactor, and §2.4 says so in as many words: *"a rename storm is
  not a pure refactor"*.
- §4.2 states that *"`dev.mode` is read only by the asset validator, the log filter and the FPS
  overlay"*. It is also read at `backtest_screen_config.py:81`, `backtest_presenter.py:398` and
  `:588`, and drives `view.set_chart_dev_mode()` → `chart_card.set_dev_mode()` on every backtest
  chart. D14's restart therefore changes backtest behaviour too — a third undeclared user-visible
  effect.
- HLD §5.3 still reads *"until a second application needs it"*; §8.5 and `hld-04b` both say it is
  superseded by §8.3, but §5.3 itself carries no marker, so a reader who starts at §5 takes away the
  wrong rule.
- D7 says tests mirror the module path within each tier, while §6.1 puts the new guards in
  `tests/unit/architecture/`, which mirrors nothing; the five existing guards stay scattered
  (`tests/unit/application/test_application_layer_structure.py`,
  `tests/unit/infrastructure/binance/test_only_the_session_factory_constructs_binance_client.py`, …).
- `EPIC-025` README §2 targets *"a module list in `shell/`, ≤ 100 lines"* for the composition root,
  while HLD §6.2 targets **deleted** at Phase 4.
- HLD §3.5 and `EPIC-025D` say the backtest screen is 60 files; it is 74.

---

## 7. Measurements to re-verify

### 7.1 "59 duplicates" — reproduces exactly, but the metric will not survive the migration

**59 is reproducible.** Defining a duplicate as *a method name defined in more than one screen whose
defining-screen set is exactly `{dashboard, trading}`* — the definition `PRO-004` §1 states — an AST
scan of `src/presentation/ui/screens/` returns **59** today. (The broader count returns 130 against
`PRO-004`'s 132; three days of commits explain the drift.) The same intent under other plausible
definitions returns 38, 94 or 150, so the number is definition-bound in a way the documents do not
record.

**The problem is not the number, it is the criterion.** `EPIC-025B` makes *"59 → 0"* Phase 1's
completion test, and Phase 1 renames `screens/trading` and `screens/dashboard` to
`shell/surfaces/trading` and `shell/surfaces/dev_board`. Any script that scans `screens/` therefore
returns 0 after the move **whether or not any duplication was removed**. The criterion is currently
satisfiable by `git mv`.

**Fix, in Phase 0, before the first move:** commit the script, defined over `screens/*`,
`modules/*` and `shell/surfaces/*` together, and record its Phase 0 output as the baseline in the
pull request.

### 7.2 "Dead — delete (measured: zero references)" — wrong for three of seven

HLD §3.5's final row lists code to delete during the phase that owns it. Three entries are live:

| Listed as dead | Actually used at | Phase that would delete it |
| :--- | :--- | :--- |
| `services/rate_limiter` | `use_cases/sync/bulk_sync_market_data/handler.py:16,73` (`ThreadSafeRateLimiter`) | **Phase 0 — `market_data`** |
| `services/position_state_reconciler` | `infrastructure/binance/futures_user_data_stream.py:65` | Phase 1 — `trading` |
| `services/strategy_factory` | `cli/trade_once_cmd.py:21`, `services/live_strategy_factory.py:42` | Phase 2 — `strategy` |

Only `system_error_feed` / `system_error_report` and the two order events look genuinely
unreferenced. `RunBacktestCommand` is bound at `binance_bot_module.py:575` and has tests, so §3.4's
*"bound but dispatched by nobody"* is right where §3.5's *"zero references"* is not. Re-run
`grep -rn <name> src/ tests/` per row before each phase, and do not copy §3.5's list into a task
file unedited.

### 7.3 The "wrong-direction import" evidence does not exist — and a real one does

HLD §2.3 and §3.4 both state that *"`domain/strategies/strategy_context.py` and three strategies
import types from `domain/backtesting`"*, and `EPIC-025D` §1.3 makes reversing it a deliverable.
Measured, at `17be6674` **and** at the ADR-date revision `03d9d9fd`: `strategy_context.py` imports
only `MarketData`, `MACDValue`, `support_resistance` and `PositionSide`, and **no file under
`src/domain/strategies/` mentions `backtesting` at all**.

The real wrong-direction import is elsewhere and is more serious:
`src/domain/trading/policies/position_sizing_bridge.py:21` imports
`domain.backtesting.policies.margin_risk_policy`. That is **`trading → backtesting`**, a dependency
§2.1 says cannot exist (*"depends on no business module"*) and that no diagram draws. Its docstring
records it as deliberate (`EPIC-021G`: *"reusing backtesting's own `PositionSizing`/`MarginRiskPolicy`
rather than inventing a second sizing model live trading would have to keep in sync"*). Phase 1 meets
it on its first day, and §2.4's promotion of `PositionSizing` into `core/vo` does not resolve it,
because `MarginRiskPolicy` is behaviour and `core/` forbids business logic.

**This needs a decision before Phase 1**, and it is a design choice rather than a documentation fix:
duplicate the policy into `trading/domain`, or extract it into a `support/` package both contexts
may use.

### 7.4 Smaller doubts

- **"~3,900 tests"** (§6.4): measured 3,020 `def test_` across 393 files. Parametrisation plausibly
  accounts for the rest, but the number sizes the riskiest line item in the plan, so it is worth one
  `pytest --collect-only -q` to confirm.
- **"0 screens import another screen's internals"** (ADR §1): confirmed by AST scan; the single
  cross-reference is a comment, as `PRO-004` says.
- **`ISymbolMarketMetadataCache` is never registered in DI** (§3.4): confirmed — the fallback at
  `backtest_presenter.py:386` is real, and it silently constructs `InMemorySymbolMarketMetadataCache`.
- **`dev_probe` "replaces nothing"** (§4.3): accurate as written — there is no probe *UI*. Worth
  noting that the practice already exists as scripts (`scripts/epic021a_venue_probe.py`,
  `epic021b_credentials_probe.py`, `epic021c_metadata_probe.py`, `epic021h_user_stream_probe.py`),
  and the design does not say what becomes of them once `dev_probe` exists.

---

## 8. Precedent check

| Mechanism built | Closest precedent | Deviation, and why it matters |
| :--- | :--- | :--- |
| Module base | Spyder `SpyderPluginV2` (`api.py` + container + registries); `lato` `ApplicationModule`; the Engine's own `IExtension` | Reusing `IExtension` instead of inventing a third contract is right and well argued (D2). Deviation: `contribute`/`subscribe` are appended to the lifecycle with no ordering contract, where Spyder separates `on_initialize` from `on_plugin_available`. The SDD permits `resolve()` inside `contribute()`, which makes contribution order observable — so the module list is load-bearing for more than topology. Say so. |
| Contribution registry | napari/`npe2` static manifest; the VS Code `contributes` block | §7.4 identifies the property to copy — the host knows what a plugin offers **without importing it**. The design then places a live `Callable` in the descriptor, so the manifest is code rather than data and the UI map cannot be read without importing every module's widget tree. This is the root of §2.3 and §5.5. A `factory_ref` (module path plus attribute) resolved lazily would restore it; failing that, `TYPE_CHECKING` annotations plus lazy imports inside `contribute()`. |
| Place vocabulary | VS Code `viewsContainers`/`views` and `menus` groups; Eclipse perspectives and placeholders; napari dock areas | The fixed vocabulary and "geometry belongs to the place" are faithful. Deviation: VS Code orders with a per-extension `group@order` **string**, never a shared global integer, precisely so two independently authored extensions cannot collide. See §3.4. |
| Guards with a ratchet allowlist | ArchUnit `FreezingArchRule`; `tach sync` baseline; import-linter | Choosing hand-written `ast` over `tach` is a defensible user decision, and §7.2 records the reversal path honestly. Deviation: the baseline's identity and unit are undefined. See §6.6. |
| Symbol lease | A keyed lease or lock table (Chubby, ZooKeeper ephemeral nodes); ownership-by-key in exchange OMS designs | The cited local precedent, `ActionOwnershipTracker`, has the **opposite** semantics. This matters more than any other deviation in this table, because refuse-versus-supersede is the entire safety property, and the specification's own worked example — `EPIC-024B` §4.1.2's *hard block* — only holds under refusal. |

---

## 9. Findings ranked by cost if wrong

| # | Finding | Section | Rank |
| :-: | :--- | :--- | :--- |
| 1 | SDD-03's DI-singleton coordinator breaks `async-ui-action-rule` §2 and ADR D12, changes behaviour, and leaves surfaces with no owner for action bookkeeping | §2.2 | **BLOCKER** |
| 2 | Non-probe `dev_board` contributions raise `ContributionError` when `dev.mode` is false; the application cannot boot in user mode | §2.1 | **BLOCKER** |
| 3 | `core/contracts` fails Phase 0's own Qt-free guard (`QWidget`, `QtEventBridge`) | §2.3 | **BLOCKER** |
| 4 | `shell/workbench` cannot import `PageShell` and remain lift-ready; lift criterion 1 is unsatisfiable | §2.4 | **BLOCKER** |
| 5 | Support packages and the shell contribute UI but have no `contribute()` hook and no `module_id` | §2.5 | **BLOCKER** |
| 6 | `rate_limiter` / `position_state_reconciler` / `strategy_factory` are marked dead but are live, in Phases 0, 1 and 2 respectively | §7.2 | **MAJOR** |
| 7 | A real `trading → backtesting` import exists at `position_sizing_bridge.py:21`; the documented `strategy_context` violation does not | §7.3 | **MAJOR** — before Phase 1 |
| 8 | No threading contract for ports, while the order path runs on the websocket thread | §5.1 | **MAJOR** — before Phase 1 |
| 9 | The `59 → 0` criterion is satisfiable by moving files; the script is not in the repository | §7.1 | **MAJOR** — Phase 0 |
| 10 | A global integer `order` with fail-fast collision; two statements of the uniqueness key | §3.4, §6.3 | **MAJOR** |
| 11 | `contribute()` must not eagerly import widget modules, or `PresenterManager`'s laziness is lost | §5.5 | **MAJOR** |
| 12 | `--dev` survives the restart; `sys.argv[1:]` drops the script path | §6.7 | **MAJOR** |
| 13 | No guard rule for the legacy tree during the strangler period | §5.7 | **MAJOR** — Phase 0 |
| 14 | No bridge from `AbstractScreenModule` into `IContributionRegistry` in Phase 0 | §5.4 | **MAJOR** — Phase 0 |
| 15 | A second venue is not a local change; two strategies on two symbols is not a local change | §4.1, §4.4 | **MAJOR** |
| 16 | "Owner id" names three mechanisms; the lease's cited precedent has inverted semantics | §6.1 | **MAJOR** |
| 17 | The allowlist has no defined unit or entry format | §6.6 | **MAJOR** — Phase 0 |
| 18 | `TradingSessionState`'s fan-out is roughly half the documented figure | §6.4 | **MAJOR** |
| 19 | Configuration is read twice today; "read once" is an undeclared behaviour change | §6.8 | **MAJOR** |
| 20 | `backtesting` contributes to the `trading` surface, against §4.6.4 | §6.5 | **MAJOR** |
| 21 | `system_controls` / `probes` / `sections` / `welcome` slot drift between text and diagrams | §6.2 | MINOR |
| 22 | Everything in §6.9, and the smaller doubts in §7.4 | §6.9, §7.4 | MINOR |

---

## 10. Verdict

**Not yet — but the gap is an editing pass, not a redesign.**

The strategic work is finished and finished well. The cut is justified by evidence a reviewer can
re-run rather than by assertion; the five-questions–five-tools framing is honest about applying
named patterns instead of inventing them; the build-or-buy survey does the thing almost nobody does
and records the **rejections**, so the next person does not repeat the search; and the phase plan
keeps the application runnable at every step with a real user exercising Testnet daily. Judged
against the author's own criterion — afraid of bad design, of not being able to extend, of being
hard to maintain — this specification is the opposite of what it fears. Not one of the six decisions
in §3 needs reversing: three are accepted outright and three need a clause each.

What stops Phase 0 is that five findings are genuinely blocking and four of them land in the very
first files the phase writes. The descriptor cannot be typed as specified without failing its own
guard; the surface runtime cannot be lift-ready and build a `PageShell` at once; the registry as
specified refuses to boot in ordinary user mode; support packages have no way to contribute the
widgets three diagrams show them contributing; and SDD-03 specifies precisely the thing
`async-ui-action-rule` §2 was written, after five bugs, to forbid. Each has a smallest fix of one to
three sentences.

**The round-3 pass, concretely:** `Docs/SDD/README.md` (validation rule 3, the descriptor's
`TYPE_CHECKING` annotations, SDD-03's coordinator ownership, the uniqueness key, the restart
command); HLD §4.2 and §4.6.1 (the `system_controls` / `welcome` drift); §6.1 (guard scope over the
legacy tree, and the allowlist's unit and entry format); §8.3 (the lift criterion); §3.2 (a module's
storage); plus the one decision that is not a documentation fix — what to do about
`position_sizing_bridge.py:21` before Phase 1 begins. Commit the duplicate-counting script and the
guard-entry format **before** the first `git mv`, and Phase 0 is ready to start.
