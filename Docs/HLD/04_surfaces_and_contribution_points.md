# §4 — Surfaces and contribution points

> **Rendering superseded by §11 (2026-09-13, ADR D20–D22):** the places, surfaces and the
> contribution mechanism below stand; where this section says `PageShell`, *panel* or QML, read
> `QMainWindow`, *panel* (a `QDockWidget`) or *dialog*, native OS theme, no QML. §11 has the
> mapping table.

- **Diagrams (component, PlantUML) — high view first, detail second:**
  [`hld-03a_place_vocabulary.puml`](diagrams/hld-03a_place_vocabulary.puml) — the vocabulary of
  places a module may ask for, the one descriptor shape they share, and the two things that are
  deliberately *not* places (§4.6.1);
  [`hld-03b_contribution_matrix.puml`](diagrams/hld-03b_contribution_matrix.puml) — what each
  surface receives, place by place, coloured by the module that owns the widget (§4.6.2, §4.6.4);
  [`hld-05a_window_containment.puml`](diagrams/hld-05a_window_containment.puml) — what contains
  what: `MainWindow` ⊃ Sidebar + `QStackedWidget` ⊃ surfaces and module-owned screens ⊃ `PageShell`
  slots, plus the registry that feeds every slot. (`hld-05b_trading_devboard_slots.puml`, which
  drew Trading and the Dev Board slot by slot, was deleted with the Dev Board in `EPIC-033P`; §4.5's
  table is where each of its widgets lives now.)

## 4.1 The problem, measured

> **Resolved.** The problem below was measured in 2026-09. The single Trading screen became two
> desks (`EPIC-028`), the Dev Board's parts moved to the desks, the Market mode and the Developer
> mode, and `EPIC-033P` stage 3 deleted the Dev Board; `test_presenter_duplication_only_shrinks.py`
> holds what is left of the duplication. Kept as the reason the contribution mechanism exists.

Trading (`screens/trading`) and Dev Board (`screens/dashboard`) built **one** set of business
behaviour twice. Fifty-nine method and member names are duplicated between them; both use the
same `PositionsPanel` and `OpenOrdersPanel`; the equity chart is built with the same recipe (a
comment says so: *"same construction recipe"*); the strategy panel has the same eight object names
in both; the session panel and last-signal panel docstrings say *"mirrors"*. `DashboardPresenter` is
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
| `welcome` 🔵 (ADR D13) | `HEADER` (environment banner, developer-mode switch — ADR D14) · `WORKSPACE` (app name and version, **Start**) | always | ✅ **default**; Start opens the Futures desk (`trading.futures`, since `EPIC-028M`) |
| `trading` | `HEADER` (+ `STATUS_TILE`) · `CONTEXT_BAR` · `WORKSPACE` (chart) · `RAIL` (panels) · `CONSOLE` · `MODAL` | always | no. The declared place family of the two desks (`trading.futures`, `trading.spot`, `EPIC-028K`/`028L`), which are still `PageShell` screens: they move onto this surface when `EPIC-025` converts the remaining `PageShell`s. The single Trading screen that once rendered it left in `EPIC-028M` |
| `bots` (`EPIC-029F`, ADR D19) | not a surface yet: a `PageShell` screen at NAVIGATION item 18 whose header holds **New bot** and whose workspace is the list of bots beside one bot's detail shell (header and actions, figures, and Chart, Parameters, Orders, Fills, Log and Backtest tabs). The Parameters tab hosts the kind's own editor and the Backtest tab the kind's own backtest (`EPIC-029D`; hidden for a kind without one), both chosen by `kind_id` (`bots/ui/kinds/kind_panels.py`), so the shell names no kind | always | no |
| `developer` (`EPIC-033P`) | `WORKSPACE` (the event log) · `DEV_PROBE` (the modules' probes, docked right) | **`dev.mode` at boot** (ADR D14): with it off the surface drops every contribution and the Developer mode screen is dropped with its commands (`ScreenContribution.gated_by`) | no |
| ~~`dev_board`~~ (deleted, `EPIC-033P`) | the Dev Board's: `trading`'s places plus `DEV_PROBE`, never gated; its parts moved to the desks, the Market mode and `developer` | — | — |
| ~~`settings`~~ (deleted, `EPIC-033E`) | none: each module contributes a page of Tools → Options through `contribute_options_page`, and the Options dialog drives the page (apply, revert, dirty) | — | — |

⚠️ These are changes in **user-visible behaviour**, not pure refactoring, decided by the user on
2026-09-13 (ADR D13, D14): the app opens on a Welcome screen; the developer surface and every API
probe exist only when `dev.mode` was true at boot (the Developer mode since `EPIC-033P`); the Welcome screen carries the developer-mode switch, which
writes `user_config.json` and offers a restart. The Welcome screen is a **shell** surface (it is
about the application, not about any bounded context) and its primary action is **Start** — not
"Login" — until there is something to authenticate; the button raises one `StartRequested` intent
so a real login can replace it later without moving anything else.

**A widget contributed to a surface belongs to a module.** For example, `trading` builds the
same `PositionsPanel` on both desks — one class, two instances, one `LiveOrderBookCoordinator`
(in `modules/trading/ui/`). Duplication drops to zero because there
is nothing left to copy.

## 4.3 Contribution points — the round-1 kinds (❓ O1: the final schema is settled in round 2)

The mechanism: a module declares a **description** (a frozen dataclass descriptor) plus a factory;
the surface or shell renders it. The principles are borrowed from the Engine's `EPIC-001D`: *"Python
describes, QML renders"*, *"the registry is for genuinely dynamic surfaces"*, *"regions decide
geometry"*.

| Kind | Descriptor (draft) | Contributed by | Rendered by | Replaces today |
| :--- | :--- | :--- | :--- | :--- |
| `screen` | `route, title, icon, section_key, sequences, is_default, factory(container) -> (View, Presenter)` | every module | the shell (`ScreenRegistry` ✅ from `EPIC-016` — kept until Phase 5) | the hard-coded tuple of 5 modules at `app_bootstrapper.py:322` |
| `surface_widget` | `surface_id, slot, order, factory(container) -> QWidget, owner_module` | market_data, trading, strategy, charting, indicators | a surface | two Presenters building their own panels |
| `options_page` | `contributor_id, order, factory(container) -> IOptionsSection` (a page bound to the **module's own** config keys) | trading (venues, credentials check), market_data (venue, default symbols / interval / sync days) ✅ `EPIC-033E`; it was the `settings_section` kind from `EPIC-025E` PR 4.4e | the Options dialog (Tools → Options) | a single `SettingsView` grid that knew every config key, then one Settings screen with a Save button per section |
| `dev_probe` 🔵 | `title, module_id, factory(container) -> QWidget` | any module with an exchange API it does not yet understand | the `developer` surface, the Developer mode's right dock area, only under `dev.mode` (`EPIC-033P`; the Dev Board's probes slot before) | **nothing** (measured: the app has no probe or raw-endpoint UI at all) |
| `cli_command` | `name, build_parser(sub), execute(app, args)` | market_data (`sync`, `stream`), trading (`exchange-status`, `order-preview`, `order-dry-run`), strategy (`trade-once`) | `shell/cli` | the if/elif chain at `main.py:139-156` plus `cli_commands.json` |
| `status_tile` | `key, factory -> QWidget` | trading (websocket pill), market_data (price ticker) | a surface header | the Dev Board's header actions (`DevBoardPanel.header_actions`, deleted with it in `EPIC-033P`) |

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
- No probe is loaded when `dev.mode` is false: the `developer` surface (the `dev_board` one before
  `EPIC-033P`) does not exist, so its factories never run, and the Developer mode screen itself is
  dropped with its commands (`ScreenContribution.gated_by`).

## 4.5 Who owns which widget (the desks, the Market mode and the Developer mode)

The single Trading screen became two **desks** in `EPIC-028` (the
[ADR](../../Tasks/epics/EPIC-028_futures_and_spot_trading_desks/DECISION_2026-09-29_two_trading_desks.md)):
the Futures desk and the Spot desk, one composition (`ui/desk/desk_screen/`) built for one venue
each, differing only in their `DeskProfile` (ADR D5). Every widget on a desk is its own venue's.

| Widget | Owning module | Each desk | Elsewhere |
| :--- | :--- | :-: | :--- |
| Chart panel (one symbol) / chart tabs (n symbols) | `charting` (host) + `market_data` (feed) | 1, its venue's market | the Market mode: a tab per open symbol, Spot or Futures (`EPIC-033H`, `033Q`) |
| Positions table, open orders table (with cancel-one-order) | `trading` | ✅ account tabs: open orders (cancel one, cancel all), order and trade history, positions (close at market) or assets | — |
| Account summary (available, wallet, margin, uPnL / quote free, locked, equity) | `trading` | ✅ | — |
| Order panel (every order type the venue takes, estimates, TP/SL on Futures) | `trading` | ✅ in the rail; Trade → New order… (`F9`) focuses it (`EPIC-033R`) | — (ADR D15's "Dev Board only" manual-order card was retired in `EPIC-028M`) |
| Enable/Disable, Emergency stop | `trading` | ✅ for its venue only | — |
| Session state (enabled, orders sent, symbols held) | `trading` | — | the Developer mode's *Trading session* probe |
| Equity chart | `trading` (adapter) + `charting` | ✅ its venue's curve | — |
| Strategy panel, parameters dialog | `strategy` | ✅ its venue's arming (`desk/strategy_card/`, until Bots takes it, HLD §11.2.4) | — |
| Strategy overlay on the chart | `strategy` | ✅ | — |
| Indicator script checklist, indicator parameters | `indicators` | — | the Market mode's Indicators panel and Tools → Indicator parameters… (`BOT-153`) |
| Watchlist | `trading` | a reduced context bar (symbol) | the Market mode's Watchlist panel |
| API probes, event log | each module; the shell | — | the Developer mode, only under `dev.mode` (`EPIC-033P`) |
| Log console | `ui_kit` | ✅ | ✅ every mode's channel of the one Output pane |

The Dev Board, the developer testbed that held a column of this table until `EPIC-033P` stage 3,
is deleted: what it showed moved to the desks, the Market mode and the Developer mode, and its
*Last signal* read-out was dropped (the user's decision, 2026-10-05).

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
connection, `WORKSPACE` the one big thing, `NAVIGATOR` the left panels the centre is picked or set up from, `RAIL` the column of panels, `CONSOLE` the log, `MODAL` a
dialog the page opens; `STATUS_TILE` and `DEV_PROBE` are the two places outside the page shell, and a
page of Tools → Options is a contribution of its own, not a place (`EPIC-033E`). Two things are **not** places, on purpose: a free-form docking area (a
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
   contributes **panels into `trading.rail`**;
   only `market_data` and `charting` may contribute to `workspace`, because a workspace holds one
   thing. Examples: `trading` (positions, orders, session), `strategy` (the strategy panel, the last
   signal). A hypothetical `risk` module (exposure limits) would answer yes with one panel.
3. **Is the rest configuration or diagnostics?** Then an Options page, `status_tile`, and
   a `DEV_PROBE` on the `developer` surface respectively. Every module with configuration keys answers yes to the first.

A module may answer yes to several: Backtest has its own screen **and** a status tile. **When in
doubt, start as a probe.** Something not yet proven is a `DEV_PROBE` on the `developer` surface
first (gated by `dev.mode`) and becomes a panel of its mode when the user wants it there. This is
what "the developer's screen is for testing and discovery" (ADR D4) means in practice; the Dev
Board that ADR D4 named was deleted in `EPIC-033P`, and the Developer mode carries its testing role.

### 4.6.3 Five rules that keep the vocabulary honest

1. **Geometry belongs to the place, content to the module.** A module never sets a width, a
   height or a position. It declares `place`, `order` and a size *hint* (`compact` / `regular` /
   `tall`); the place resolves it. This is the general form of the `BOT-128` lesson (two tables lost
   four of seven columns because a screen hand-sized them) and of `EPIC-001D`'s "regions decide
   geometry".
2. **One widget, many places.** The same factory may be contributed to several surfaces; a module
   never builds one version of a widget per screen. The two desks show one order panel, one set of
   account tabs and one strategy card, each built for its own venue.
3. **Every screen is a surface.** A module's own screen is a `PageShell` like any other, and the
   owner declares which of its slots accept contributions from other modules
   (`accepts=("rail", "modal")`). That is how `strategy` puts its parameters dialog into Backtest
   and `market_data` puts sync progress there, without Backtest importing either.
4. **A module's UI footprint is readable in one place.** `module.contribute()` is the only method
   that registers UI; reading it tells you everything the module puts on screen. A guard renders
   the *UI map* — a table of surface × place × module — and fails on a widget that is contributed
   nowhere or a place that does not exist.
5. **The shell renders; modules never reach into another module's widgets.** Coordination between
   two panels on the same rail happens through events and ports (§2.5, §3.4), never through the
   surface handing one widget a reference to another.

### 4.6.4 The existing modules, checked against the rule

| Module | Q1 own screen | Q2 trading panels | Q3 config / diagnostics | Matches today? |
| :--- | :--- | :--- | :--- | :--- |
| `market_data` | ✅ Data Management (the Watchlist is a panel of `trading`'s Market mode since `EPIC-033H`) | context bar (symbol); the market's candles reach the Market mode's charts through its feed (support packages never contribute — the needing module does) | Options page (venue, defaults); status tile (ticker) | ✅ |
| `trading` | ❌ — Trading is a **surface**, not the module's screen | positions, orders, manual order, session, equity | settings section (venue, limits, credentials check); status tile (websocket); probe | ✅ once Trading is a surface (Phase 1) |
| `strategy` | ❌ | strategy panel; modal (parameters) | — | ✅ |
| `backtesting` | ✅ Backtest | ❌ (its run-progress tile goes on **its own** screen's header, not Trading's) | status tile on its own screen | ✅ |
| `indicators` (support) | — | never contributes; `trading`'s Market mode shows the checklist | — | ✅ |
| `charting` (support) | — | never contributes; the module that wants a chart contributes it (`trading` on the desks and in the Market mode) | — | ✅ |
| *shell* (not a module): the Developer page of Tools → Options | — | — | — | the rule's own test: what is about the application itself belongs to the shell. The `welcome` and `settings` surfaces that held it were deleted by `EPIC-033C` and `EPIC-033E` |

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
