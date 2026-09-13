# Vocabulary — the words this project uses, and what each one means

- **Purpose:** one place to look a term up while developing, and the **only** place a term is
  defined. Other documents (HLD, SDD, ADRs, task files) use the terms and link here; they do not
  redefine them. This is the same rule `CLAUDE.md` applies to rule files: a second copy drifts.
- **When to edit:** the commit that introduces a new term — in a document, an enum, a class name
  that other modules will see — adds its row here. A term that is not in this file is not yet
  part of the project's language.
- **How a row is written:** the term as it appears in code or documents; a one- or two-sentence
  definition a newcomer can act on; who owns it; where it is defined in code or design; and, where
  a confusion has actually happened, what it must not be mistaken for.
- **Language:** English (`ONBOARDING.md` §10). Where the user coined a term in Vietnamese, the
  original is quoted once.

Sections: [1 Architecture](#1-architecture-terms) · [2 Workbench (UI places)](#2-workbench-ui-places)
· [3 Domain — per bounded context](#3-domain-terms-per-bounded-context) · [4 Process](#4-process-terms)

---

## 1. Architecture terms

| Term | Definition | Owner | Defined in | Not to be confused with |
| :--- | :--- | :--- | :--- | :--- |
| **Bounded context** | A part of the system with its own language: at least one word means something different here than elsewhere, to the point that the code keeps two types. Cut by the six criteria C1–C6. | — | HLD §1 | a *screen* (a place to hang widgets) or a *layer* (a technical kind) |
| **Module** (`modules/<id>/`) | The code unit that owns one bounded context: `contracts/`, `domain/`, `application/`, `adapters/`, `ui/`, `module.py`. Exactly four exist: `market_data`, `trading`, `strategy`, `backtesting`. | — | HLD §3.2 | a *support package* (technical, no business language); an Engine `IExtension` in general |
| **`module_id`** | The module's public name, stable forever: used in routes, persisted ui_state, event names, owner ids. Renaming is a breaking change with a state migration. Only the four modules have one; a support package does not, and the shell contributes under the literal `"shell"`. | each module | HLD §3.1 | the Python package name (may differ); a `contributor_id` (below) |
| **`contributor_id`** | The field on a contribution that says who made it: a `module_id`, or `"shell"` for the shell's own surfaces. Support packages never contribute — the module that wants a support widget contributes it. | — | SDD descriptor | a `module_id` in general |
| **`BoundedContextModule`** | The application's module base class: the Engine's `IExtension` plus two UI hooks, `contribute()` and `subscribe()`. | `core/contracts` | HLD §3.1, SDD-01 | the Engine's legacy `IModule`; `AbstractScreenModule` (a screen, from `EPIC-016`) |
| **Support package** (`support/<name>/`) | A technical capability many contexts use, with no business language of its own (criterion C6 fails): `binance_gateway`, `charting`, `indicators`, `ui_kit`. Has `contracts/`, may never contain a business rule. | — | HLD §1.2, §2.2 | a bounded context |
| **Kernel service** | A cross-cutting service injected into modules, never a module itself: DI container, event bus, config, logging, thread manager, scheduler, navigation, health. Provided by the Engine. | Engine | HLD §2.2 | — |
| **`core/`** | The application's kernel *policy*: `core/contracts/` (module base, contribution registry, engine-adapter ports) and `core/vo/` (the Published Language). Imports nothing from `modules/`, `support/` or PySide6. | shell | HLD §3.4 | the Shared Kernel (below) |
| **`shell/`** | Robert Martin's "Main" component: the only code that knows every module. Holds the explicit module list, the surfaces, the CLI assembly. | shell | HLD §2.1 | `main.py` alone |
| **Contract** (`contracts/`) | The only importable surface of a module: ports, DTOs, events. Everything else in the module is internal. | each module | HLD §3.3 | the module's `application/` use cases (internal) |
| **Port** | An abstract base class named `I*`, the typed request/response contract between modules; the owning module implements it and registers it in DI during `register()`. | owning module | HLD §3.3, `architecture-rule.md` §2.1 | a Command or Query class (internal to a module) |
| **DTO** | A flat, frozen dataclass carried across a module boundary. Never an entity. | owning module | HLD §3.3 | an entity or aggregate |
| **Published Language** (`core/vo`) | Value objects neutral to any business language, immutable, read by every module, owned by none: `TimeFrame`, `OrderSide`, `PositionSide`, `MarketDataVenue`, `TradingVenue`, `Currency`, `MarketType`, `MarketData`, `PositionSizing`. Admission: two consumers in two modules, measured. | nobody | HLD §2.4 | the Shared Kernel |
| **Shared Kernel** | In this repository, **exactly two** Engine symbols — `IDomainEvent`, `BaseEvent` — and a test locks that. Do not use the phrase for anything else. | Engine | `architecture-rule.md` | the Published Language |
| **Customer / Supplier** | Two contexts where the downstream (customer) depends on the upstream's contracts and the upstream does not know the customer exists. `strategy` is a customer of `trading`. | — | HLD §2.3 | — |
| **Open Host Service** | A context that publishes a general-purpose API for many consumers, in the Published Language. `market_data` is one. | — | HLD §2.3 | — |
| **Anticorruption Layer (ACL)** | A translation layer that keeps another model from leaking in: `binance_gateway` around the SDK; `backtesting/adapters` translating `PaperExchange` into `StrategyContext`. | the downstream side | HLD §2.3 | — |
| **Seam** | The extension point built on the first case: a port, a base class, a place enum, a list a new case is added to. Mandatory (Open/Closed). | — | `architecture-rule.md` §7.2.1 | a *variant* (below) |
| **Variant** | A second implementation or a feature nobody has asked for. Built only when a real case arrives (YAGNI). | — | `architecture-rule.md` §7.2.1 | a seam |
| **Verified fake** | The one in-memory implementation of a public port that ships with the port under `contracts/testing/`, and passes the same **contract suite** the real implementation passes. Consumers test against it; nobody `Mock`s a foreign port. | the provider module | HLD §10.3 | a `Mock(spec=IPort)`; a stub a consumer wrote for itself |
| **Contract suite** | The test module for one port, parametrised over `[fake, real]`, written by the provider and extended by consumers with the guarantees they rely on. | the provider module | HLD §10.3 | a unit test of the implementation |
| **Guard** | An architecture fitness function: a test, written with `ast`, that fails when a structural rule is broken. Three exist for the module split; their allowlist may only shrink. | `tests/unit/architecture` | HLD §6.1 | a unit test of behaviour |
| **Allowlist ratchet** | The list of known violations recorded when a guard is introduced; the guard fails on any new violation and on any listed violation that no longer exists, so the list can only shrink. | — | HLD §6.1 | a permanent exemption list |
| **Symbol lease** | `trading`'s record that one `owner_id` currently holds a symbol: an **exclusive lease that refuses** a second claimer (`SymbolAlreadyLeased`) and refuses orders from any other owner. `strategy` claims on arm, releases on disarm; a manual order carries `owner_id="manual"`. The holder is not exposed on the public port. | `trading` | HLD §3.4, SDD-04 | the two mechanisms below, which have different semantics |
| **Stream owner** (`IMarketStream.owner_id`) | A **namespace**: starting a stream replaces that owner's previous subscriptions and never touches another owner's; two owners may stream the same symbol; one owner may hold several streams. Today's `StartLiveStreamCommand.owner`. | `market_data` | SDD-06b | an exclusive lease |
| **Action ownership** (`ActionOwnershipTracker`) | A **fencing token** that *supersedes*: a second `begin_action` invalidates the first (`action_superseded`, `ActionOutcome.INVALIDATED`). Correct for UI actions; the **opposite** of a lease — never copy its shape for a resource that must refuse. | the card's Presenter | `ui/common/action_ownership_tracker.py` | the symbol lease |
| **Owner id** | The string naming who holds one of the three above. Stable, human-readable, usually a `module_id` or `"manual"`. Which semantics apply depends on the mechanism, not on the string. | the mechanism's module | HLD §3.4, SDD-06 | — |

## 2. Workbench (UI places)

The workbench model: the shell owns a small, fixed vocabulary of **places**; a module **chooses**
places, it never invents layout (HLD §4.6). Adding a place is an HLD change, not a module change.
This table is the canonical definition of the `Place` enum (SDD-01).

| Term | Definition | Geometry decided by | Exists today |
| :--- | :--- | :--- | :--- |
| **Surface** | A screen with **no business logic**: it lays out a `PageShell`, asks the registry who contributes into each of its slots, and builds the widgets through the factories it is given. Shell-owned surfaces: `welcome`, `trading`, `dev_board`, `settings`. | — | 🔵 (today `screens/trading` and `screens/dashboard` are ordinary screens) |
| **Module-owned screen** | A screen a module owns because it hosts a workflow the user performs for its own sake (§4.6.2 question 1): `backtest`, `data_management`. It is still a `PageShell`, and declares which slots accept foreign contributions (`accepts=(RAIL, MODAL)`). | the owning module | ✅ (`ScreenRegistry`) |
| **Place** | A named slot a module may contribute a widget to. The full list is the rows below. | — | — |
| `SCREEN` | A navigation entry that opens a full page. | the shell (`QStackedWidget`) | ✅ `ScreenRegistry`, `NavLocation` |
| `HEADER` | Actions that apply to the whole page (enable, reload, emergency stop) and `STATUS_TILE`s. | `PageShell.set_header` — one fixed-height row | ✅ |
| `CONTEXT_BAR` | The current context the page works in (symbol, connection, status). | `PageShell.set_context_bar` | ✅ |
| `WORKSPACE` | The one large thing the page is about (a chart, a table, a form). Only `market_data` and `charting` contribute here. | `PageShell.set_workspace(main, …)` — takes the remaining space | ✅ |
| `RAIL` | A column of self-contained **cards**, stacked by `order`, scrollable as a whole. Where most module widgets go. | `PageShell.set_workspace(…, rail)` — fixed width | ✅ |
| `CONSOLE` | Log and diagnostics for that page. | `PageShell.set_console` — bottom, collapsible | ✅ |
| `MODAL` | A dialog the page opens and closes; never a permanent resident. | the overlay host (`kit/overlay.py`) — sized by content, centred | ✅ |
| `SETTINGS_SECTION` | A form for one module's own configuration keys, on the `settings` surface. | the settings surface — one section per module, by `order` | 🔵 |
| `STATUS_TILE` | A one-glance indicator (websocket pill, price ticker, health) in a surface header. | the header — small, fixed | 🔵 |
| `DEV_PROBE` | An API probe widget on `dev_board.probes`, only when `dev.mode` was true at boot. | the Dev Board rail | 🔵 |
| **Card** | A self-contained widget in a `RAIL`: its own title, its own state, no reference to sibling cards. | the owning module | ✅ (`kit.Card`) |
| **Contribution** | A declaration "put my widget in `<surface>.<place>`", made once in `module.contribute()` (or by the shell) as a frozen `ContributionDescriptor` (`contributor_id`, `surface_id`, `place`, `order`, `size_hint`, `factory`, optional `title`). Validated when contributed; the factory is lazy and runs only when the surface is built. | the contributor | HLD §4.3, SDD-01 | a widget instance |
| **Contribution kind** | What a contribution *is* for the shell: `screen`, `surface_widget`, `settings_section`, `status_tile`, `dev_probe`, `cli_command`. Kinds are application policy, never Engine mechanism. | shell | HLD §4.3 | a place (where it goes) |
| **Size hint** (`SizeHint`) | `COMPACT` · `REGULAR` · `TALL` — the only thing a module may say about geometry; the place resolves it. | — | HLD §4.6.3 rule 1 | a width or a height |
| **Order** | An integer sort key within one `(surface, place)`; ties are broken by `(contributor_id, factory.__qualname__)`, so two modules choosing the same number render deterministically instead of refusing to boot. | the contributor | SDD rule 2 | a uniqueness key |
| **Card** (as a runtime object) | What a factory returns: a View and its Presenter built together; the Presenter owns its Coordinators and its action ownership. Two surfaces get two cards from one factory; they share the module's feed, never an object. | the contributing module | SDD "Ownership" | a shared singleton |
| **Mirror rule** | A `trading.rail` card is also a `dev_board.rail` card unless the module says otherwise; the reverse is not true. Same factory, two instances. | — | HLD §4.6.3 rule 2 | copying a widget |
| **Probe** (`dev_probe`) | A temporary widget a module contributes to Dev Board to try an exchange API it does not yet understand, through the module's real adapter, showing raw request and response. Deleted or kept deliberately once the use case has tests. | the contributing module | HLD §4.4 | a feature |
| **Welcome screen** | The default route: app name and version, the environment banner, **Start** (→ `trading`), the Developer-mode switch and Restart. Shell-owned. The primary action is "Start", not "Login", until there is something to authenticate. | shell | ADR D13 | a login screen |
| **Developer mode** (`dev.mode`) | A configuration key read **once at boot** by one shared `ConfigManager`; when true, the `dev_board` surface and every `DEV_PROBE` exist, and the backtest chart shows its FPS overlay. Toggled on the Welcome screen, written through `IConfigWriter` to `user_config.json`, applied by a restart that keeps the script path and strips `--dev`. `--dev` wins for the current run. | shell | ADR D14, SDD-05 | a runtime switch |
| **UI map** | The generated table surface × place × module that a guard renders; fails on a widget contributed nowhere or a place that does not exist. | guard | HLD §4.6.3 rule 4 | — |

## 3. Domain terms, per bounded context

Words that mean different things in different contexts are listed **once per context** — that
difference is the reason the contexts exist (HLD §1.2).

### `market_data`

| Term | Definition | Defined in |
| :--- | :--- | :--- |
| **Candle** / `MarketData` | One OHLCV bar for a symbol and a `TimeFrame`. The type is in the Published Language; renaming it `Candle` is a recorded candidate. | `core/vo` |
| **Symbol** | A raw string such as `BTCUSDT`. No value object exists yet (recorded candidate). | — |
| **Shard** | One SQLite file holding the klines of one symbol/timeframe range. | `adapters/persistence` |
| **Gap** / **Coverage** | A missing range inside stored klines; the fraction of a requested range that is stored. `IRangeCoverage` reports it. | `contracts/` |
| **Sync** | Fetching klines from the exchange into the shards for one symbol/timeframe/range; progress is a `SingleSyncProgressEvent`. | `contracts/IMarketDataSync` |
| **Market stream** | The live kline websocket for one symbol/timeframe, started and stopped by `owner_id`. | `contracts/IMarketStream` |
| **Market data venue** (`MarketDataVenue`) | Which endpoint set market data comes from (mainnet public, testnet). | `core/vo` |

### `trading`

| Term | Definition | Defined in |
| :--- | :--- | :--- |
| **Position** (`LivePosition`) | A position **as the exchange reports it**, read-only; the app never computes any of its fields. Leaves the module only as `PositionSnapshot`. | `domain/trading/live_position.py` |
| **Order** | A real order sent to the exchange through `IOrderSubmission` — the only path. | `contracts/IOrderSubmission` |
| **Order intent** | What a caller *wants* (side, quantity, type, price, `owner_id`) before preview and rounding. | `contracts/dto` |
| **Trading session** | The app-level state "trading is enabled", with its limits, counters and symbol leases; snapshot as `TradingSessionSnapshot`. | `contracts/ITradingSession` |
| **Trading venue** (`TradingVenue`) | Where orders go: disabled, testnet. Live is restricted by a guard. | `core/vo` |
| **Emergency stop** | Cancel everything, close positions, disable the session — one command. | `application/` |
| **Account snapshot** | Balance and margin as read from the exchange. | `contracts/IAccountSnapshot` |
| **Manual order** | An order intent with `owner_id="manual"`, from the manual-order card (Dev Board only, ADR D15). | `ui/` |

### `strategy`

| Term | Definition | Defined in |
| :--- | :--- | :--- |
| **Strategy** | A rule that turns a candle buffer and a `StrategyContext` into a `Signal`. Listed by `IStrategyCatalog`. | `domain/strategies` |
| **Signal** / `SignalAction` | A strategy's output on one candle: long, short, close, hold. | `contracts/dto` |
| **Arm** / **Disarm** | Attaching a strategy with a configuration to a symbol so that ticks produce orders; and detaching it. Arming claims the symbol lease. | `application/` |
| **Strategy context** (`StrategyContext`) | What a strategy is allowed to see: candles plus the current position expressed neutrally. Provided by `trading` (live) and `backtesting` (simulated). | `contracts/` |
| **Strategy engine** | The object that feeds candles to a strategy and emits `SignalGeneratedEvent`; built by `IStrategyEngineFactory`. | `application/` |
| **Sizing policy** (`ISizingPolicy`) | The rule that turns account balance, the strategy's sizing percent and leverage, and the margin-risk limit into an order quantity. Owned by `strategy` (ADR D17): "how much to bet" is a strategy decision; `trading` only rounds to the exchange's filters and enforces `TradingLimitPolicy`; `backtesting` uses the same rule. | `contracts/i_sizing_policy.py` |

### `backtesting`

| Term | Definition | Defined in |
| :--- | :--- | :--- |
| **Position** (`_OpenPosition`) | A **simulated** position inside `PaperExchange`, mutated by the app on every tick. A different word from trading's `LivePosition`; never merged. | `domain/backtesting/paper_exchange.py` |
| **Paper exchange** | The simulator that matches orders against candles with fee, margin and matching policies. | `domain/backtesting` |
| **Run** | One backtest execution with a configuration; produces a `BacktestResult`, metrics and a trade log. | `application/` |
| **Out-of-sample split** | Dividing the range into fit and validation parts. | `domain/backtesting` |

## 4. Process terms

| Term | Definition | Defined in |
| :--- | :--- | :--- |
| **North star** | The HLD: the one document that answers which modules, which boundaries, which criteria, which APIs. When code and HLD disagree, one is wrong and the discovering PR fixes it. The user's word: *"kim chỉ nam"*. | HLD README |
| **Walking Skeleton** | The thinnest end-to-end slice built first to prove every layer connects: Phase 0 = the mechanism plus `market_data`. | HLD §6.3 |
| **Strangler Fig** | Growing the new structure around the old and retiring the old piece by piece, so the app runs at every step. | HLD §6.3 |
| **Harvest** / **Lift** | Building a mechanism inside the app with an Engine-shaped layout and no app imports, then moving it into the Engine once the lift criterion holds (zero app imports; two surfaces or modules use it; API stable one phase). | HLD §8 |
| **Engine track** (E0–E3) | The Engine's schedule of lifts, aligned with the app phases. | HLD §8.4 |
| **Phase** (0–5) | One pull request that leaves the app running: mechanism + `market_data`; `trading` + surfaces; `strategy`; `backtesting`; `support/*`; Engine navigation. | `EPIC-025` |
| **Apply before you invent** | Survey existing solutions first; prefer applying; when not adopted, still apply the shape. | `ONBOARDING.md` §7 |
| **Documentation-only change** | A change touching only `Docs/`, `Tasks/`, `.agents/`, `CLAUDE.md`; may be committed, pushed and merged without asking. | `CLAUDE.md` item 1 |
