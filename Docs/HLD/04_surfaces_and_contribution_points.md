# §4 — Surfaces and contribution points

- **Diagrams (component, PlantUML) — high view first, detail second:**
  [`hld-03a_place_vocabulary.puml`](diagrams/hld-03a_place_vocabulary.puml) — the vocabulary of
  places a module may ask for, the one descriptor shape they share, and the two things that are
  deliberately *not* places (§4.6.1);
  [`hld-03b_contribution_matrix.puml`](diagrams/hld-03b_contribution_matrix.puml) — what each
  surface receives, place by place, coloured by the module that owns the widget (§4.6.2, §4.6.4);
  [`hld-05a_window_containment.puml`](diagrams/hld-05a_window_containment.puml) — what contains
  what: `MainWindow` ⊃ Sidebar + `QStackedWidget` ⊃ surfaces and module-owned screens ⊃ `PageShell`
  slots, plus the registry that feeds every slot;
  [`hld-05b_trading_devboard_slots.puml`](diagrams/hld-05b_trading_devboard_slots.puml) — Trading
  and Dev Board slot by slot, each widget coloured by its owning module, dotted lines joining the
  widgets that are the same factory on both surfaces.

## 4.1 The problem, measured

Trading (`screens/trading`) and Dev Board (`screens/dashboard`) build **one** set of business
behaviour twice. Fifty-nine method and member names are duplicated between them; both use the
same `PositionsPanel` and `OpenOrdersPanel`; the equity chart is built with the same recipe (a
comment says so: *"same construction recipe"*); the strategy card has the same eight object names
in both; the session card and last-signal card docstrings say *"mirrors"*. `DashboardPresenter` is
2,008 lines long, `TradingPresenter` 973.

The user's decision (ADR D4) is that Trading is the real use-case screen and Dev Board is the
developer's screen for **testing** and **discovering APIs** — in the user's words, *"nên có nhiều
cái tụi nó sẽ trùng lặp"* ("so a lot of what they show will overlap"). Overlap is **intended**. The
design requirement is that the overlap be produced by **one** widget used in two places, not by two
copies of the widget.

## 4.2 A surface is a screen with no business logic

A **surface** is a screen under `shell/surfaces/<id>/` that does exactly three things: (1) lays
itself out (a `PageShell` with named slots), (2) asks the `IContributionRegistry` "who contributes
what into which of my slots", and (3) builds each widget through the factory the module provided.
It contains **zero lines of business logic, zero business Coordinators and zero Feeds** — all of
that lives inside the widgets that modules own.

| Surface | Slots | Gate | Default route |
| :--- | :--- | :--- | :--- |
| `welcome` 🔵 (ADR D13) | app name and version · environment banner · **Start** · developer-mode switch (ADR D14) | always | ✅ **default**; Start navigates to `trading` |
| `trading` | `header` · `context_bar` · `workspace` (chart) · `rail` (cards) · `console` | always | no (reached from Welcome) |
| `dev_board` | `header` · `system_controls` · `workspace` (several charts) · `rail` · `probes` 🔵 · `console` | **`dev.mode` at boot** (ADR D14; today it is **not gated** — measured, `dev.mode` is read only by the asset validator, the log filter and the FPS overlay) | no (today it is `is_default=True`) |
| `settings` | `sections` | always | no |

⚠️ These are changes in **user-visible behaviour**, not pure refactoring, decided by the user on
2026-09-13 (ADR D13, D14): the app opens on a Welcome screen; Dev Board and every API probe exist
only when `dev.mode` was true at boot; the Welcome screen carries the developer-mode switch, which
writes `user_config.json` and offers a restart. The Welcome screen is a **shell** surface (it is
about the application, not about any bounded context) and its primary action is **Start** — not
"Login" — until there is something to authenticate; the button raises one `StartRequested` intent
so a real login can replace it later without moving anything else.

**A widget contributed to a surface belongs to a module.** For example, `trading` contributes the
`PositionsPanel` factory to both `trading.rail` and `dev_board.rail` — one class, two instances,
one `LiveOrderBookCoordinator` (in `modules/trading/ui/`). Duplication drops to zero because there
is nothing left to copy.

## 4.3 Contribution points — the round-1 kinds (❓ O1: the final schema is settled in round 2)

The mechanism: a module declares a **description** (a frozen dataclass descriptor) plus a factory;
the surface or shell renders it. The principles are borrowed from the Engine's `EPIC-001D`: *"Python
describes, QML renders"*, *"the registry is for genuinely dynamic surfaces"*, *"regions decide
geometry"*.

| Kind | Descriptor (draft) | Contributed by | Rendered by | Replaces today |
| :--- | :--- | :--- | :--- | :--- |
| `screen` | `route, title, icon, section_key, sequences, is_default, factory(container) -> (View, Presenter)` | every module | the shell (`ScreenRegistry` ✅ from `EPIC-016` — kept until Phase 5) | the hard-coded tuple of 5 modules at `app_bootstrapper.py:322` |
| `surface_widget` | `surface_id, slot, order, factory(container) -> QWidget, owner_module` | market_data, trading, strategy, charting, indicators | a surface | two Presenters building their own cards |
| `settings_section` | `title, order, factory(container) -> QWidget` (a form bound to the **module's own** config keys) | trading (venue, credentials check, limits), market_data (venue, default symbols / interval / sync days), ui_kit (theme) | the `settings` surface | a single `SettingsView` grid that knows every config key |
| `dev_probe` 🔵 | `title, module_id, factory(container) -> QWidget` | any module with an exchange API it does not yet understand | the `dev_board.probes` slot, only under `dev.mode` | **nothing** (measured: the app has no probe or raw-endpoint UI at all) |
| `cli_command` | `name, build_parser(sub), execute(app, args)` | market_data (`sync`, `stream`), trading (`exchange-status`, `order-preview`, `order-dry-run`), strategy (`trade-once`) | `shell/cli` | the if/elif chain at `main.py:139-156` plus `cli_commands.json` |
| `status_tile` | `key, factory -> QWidget` | trading (websocket pill), market_data (price ticker) | a surface header | `DevBoardPanel.header_actions` |

**Considered and not adopted in round 1.** `chart_overlay`: drawing on a chart goes through
`IChartHost`, the port of `support/charting`, which the surface hands to the widget; no separate
registry is needed yet. `health_tile`: folded into `status_tile`.

## 4.4 `dev_probe` — what "discovering an API" means, concretely

The user's definition: *"khi bạn dev nếu API nào của sàn chưa rõ, thì sẽ tạo 1 UI để test API đó"*
("while developing, if some exchange API is unclear, you build a UI to try that API out").

- A probe is **module code** (`modules/<id>/ui/dev_probes/<name>_probe.py`). It calls the module's
  **real adapter or port** — never the raw SDK; the guard *only the session factory constructs
  binance client* still applies — and shows the request that was sent, the raw response, and the
  translated error. It is living evidence of "how this API behaves" gathered before a use case is
  written against it.
- A probe's lifetime is **temporary**. Once the API is understood and the use case has tests, the
  probe is either deleted or kept deliberately as an operational tool; that choice is made in the
  pull request and written into the task. A probe must not become an unannounced feature.
- The first probe (Phase 1, `trading`) is an "Exchange API tester": pick an endpoint from the list
  the adapter already wraps (`positionRisk`, `openOrders`, the `exchangeInfo` filters for one symbol,
  `listenKey`), press the button, read the payload. This is exactly what was missing during the
  `BUG-117` investigation, where the only option was reading logs instead of calling the endpoint.
- No probe is loaded when `dev.mode` is false: the `dev_board` surface does not exist, so its
  factories never run.

## 4.5 Who owns which widget (Trading and Dev Board)

The same table as a picture: [`hld-05b_trading_devboard_slots.puml`](diagrams/hld-05b_trading_devboard_slots.puml).

| Widget | Owning module | Trading | Dev Board |
| :--- | :--- | :-: | :-: |
| Chart card (one symbol) / chart list (n symbols) | `charting` (host) + `market_data` (feed) | 1 | n |
| Positions table, open orders table (with cancel-one-order) | `trading` | ✅ | ✅ |
| Manual order card | `trading` | ❌ (user decision 2026-09-13, ADR D15: Dev Board only; adding `trading.rail` later is one line in `contribute()`, and the card depends only on trading's own ports so that line is all it takes) | ✅ |
| Session card, Enable/Disable, Emergency stop, websocket pill | `trading` | ✅ | ✅ |
| Equity chart | `trading` (adapter) + `charting` | ✅ | ✅ |
| Strategy card, last-signal card, parameters dialog | `strategy` | ✅ | ✅ |
| Strategy overlay on the chart | `strategy` | ✅ | 🔵 |
| Indicator script checklist | `indicators` | — | ✅ |
| System controls (market / symbol / date range / load / start / stop), symbol picker | `market_data` | a reduced context bar | ✅ |
| API probes | each module | — | ✅ |
| Log console | `ui_kit` | ✅ | ✅ |

## 4.6 Where a new module's UI goes — the workbench rule 🔵 Proposed (2026-09-13)

The user's concern, verbatim: *"lack of UI layout philosophy → it leads to: have no concept if we
want to add a new module that has UI; the question is, how is the UI of this module put in?"* The
sections above describe the surfaces that exist today; they do not tell the author of a **new**
module where its widgets belong. This section is that rule. It is the "workbench" model that VS
Code, Spyder and napari all converged on: **the shell owns a small, fixed vocabulary of places; a
module chooses places, it never invents layout.**

### 4.6.1 The vocabulary of places

Every place has a name, a meaning and a geometry rule, and a module may put UI only in a named
place. The list is deliberately short, and adding a place is an HLD change, not a module change.
**The canonical definition of every place — and of every other term this document uses — lives in
[`Docs/VOCABULARY/README.md`](../VOCABULARY/README.md) §2**, which is also the specification of the
`Place` enum in the SDD. It is not repeated here, so that there is one copy to keep true.

In one sentence each, so this section reads on its own: `SCREEN` is a navigation entry; inside a
page, `HEADER` holds page-wide actions and status tiles, `CONTEXT_BAR` the current symbol and
connection, `WORKSPACE` the one big thing, `RAIL` the column of cards, `CONSOLE` the log, `MODAL` a
dialog the page opens; `SETTINGS_SECTION`, `STATUS_TILE` and `DEV_PROBE` are the three places
outside the page shell. Two things are **not** places, on purpose: a free-form docking area (a
module never asks for it, even if the Engine adopts docking in Phase 5) and "the sidebar"
(navigation is derived from `SCREEN` contributions; nothing else goes there).

### 4.6.2 The three questions a new module answers, in order

A module's author answers these once, in `module.contribute()`, and the answers are the whole of
the module's UI footprint.

1. **Does the module own a workflow the user performs for its own sake** — something with a start
   and an end that is not "trading right now"? If yes, the module gets **its own `screen`**, built
   as a `PageShell`, and it is the *owner surface* of that page. Examples: Backtest (run a test, read
   the result), Data Management (sync, inspect, repair). A hypothetical `journal` module (review
   past trades) would answer yes.
2. **Does the module produce or consume something the trader needs while trading?** If yes, it
   contributes **cards into `trading.rail`** (and, by the mirror rule below, `dev_board.rail`);
   only `market_data` and `charting` may contribute to `workspace`, because a workspace holds one
   thing. Examples: `trading` (positions, orders, session), `strategy` (the strategy card, the last
   signal). A hypothetical `risk` module (exposure limits) would answer yes with one card.
3. **Is the rest configuration or diagnostics?** Then `settings.section`, `status_tile`, and
   `dev_board.probes` respectively. Every module with configuration keys answers yes to the first.

A module may answer yes to several: Backtest has its own screen **and** a status tile. **When in
doubt, start on Dev Board.** A card that is not yet proven goes to `dev_board.rail` first (gated by
`dev.mode`) and is promoted to `trading.rail` when the user wants it there — a one-line change in
`contribute()`. This is what "Dev Board is for testing and discovery" (ADR D4) means in practice.

### 4.6.3 Five rules that keep the vocabulary honest

1. **Geometry belongs to the place, content to the module.** A module never sets a width, a
   height or a position. It declares `place`, `order` and a size *hint* (`compact` / `regular` /
   `tall`); the place resolves it. This is the general form of the `BOT-128` lesson (two tables lost
   four of seven columns because a screen hand-sized them) and of `EPIC-001D`'s "regions decide
   geometry".
2. **One widget, many places.** The same factory may be contributed to several surfaces; a module
   never builds a "Trading version" and a "Dev Board version" of a widget. Trading and Dev Board
   therefore **mirror by default**: a `trading.rail` card is also a `dev_board.rail` card unless the
   module says otherwise. The reverse is not true — Dev Board holds things Trading does not.
3. **Every screen is a surface.** A module's own screen is a `PageShell` like any other, and the
   owner declares which of its slots accept contributions from other modules
   (`accepts=("rail", "modal")`). That is how `strategy` puts its parameters dialog into Backtest
   and `market_data` puts sync progress there, without Backtest importing either.
4. **A module's UI footprint is readable in one place.** `module.contribute()` is the only method
   that registers UI; reading it tells you everything the module puts on screen. A guard renders
   the *UI map* — a table of surface × place × module — and fails on a widget that is contributed
   nowhere or a place that does not exist.
5. **The shell renders; modules never reach into another module's widgets.** Coordination between
   two cards on the same rail happens through events and ports (§2.5, §3.4), never through the
   surface handing one widget a reference to another.

### 4.6.4 The existing modules, checked against the rule

| Module | Q1 own screen | Q2 trading cards | Q3 config / diagnostics | Matches today? |
| :--- | :--- | :--- | :--- | :--- |
| `market_data` | ✅ Data Management | context bar (symbol), Dev Board system controls | settings section (venue, defaults); status tile (ticker) | ✅ |
| `trading` | ❌ — Trading is a **surface**, not the module's screen | positions, orders, manual order, session, equity | settings section (venue, limits, credentials check); status tile (websocket); probe | ✅ once Trading is a surface (Phase 1) |
| `strategy` | ❌ | strategy card, last signal; modal (parameters) | — | ✅ |
| `backtesting` | ✅ Backtest | ❌ | status tile (run in progress) | ✅ |
| `indicators` (support) | ❌ | Dev Board checklist card | — | ✅ |
| `charting` (support) | ❌ | `workspace` of Trading, Dev Board, Backtest | — | ✅ |
| *shell* (not a module): `welcome`, `settings` | — | — | — | the rule's own test: surfaces about the application itself belong to the shell, exactly as `welcome` does (ADR D13) |

The check exposes the one place the current code disagrees with the rule: the Trading screen is
owned by nobody today (it is a `screens/trading` package that rebuilds `trading`'s and
`strategy`'s widgets), which is the 59-duplicate problem in another form. Under the rule it is a
surface owned by the shell with no logic of its own, exactly as §4.2 says.

### 4.6.5 What this settles for round 2 (❓ O1)

The contribution-point kinds in §4.3 are the *places* above plus `cli_command`. The descriptor
schema for every place-kind is the same four fields — `place`, `order`, `size_hint`, `factory` —
plus `module_id` and, for `screen`, the navigation metadata `ScreenRegistry` already takes. That
uniformity is the answer to O1: **one descriptor shape, a place enum, no per-kind schema** beyond
`screen`.
