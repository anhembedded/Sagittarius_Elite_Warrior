# §11 — The desktop workbench: QtWidgets only, the OS theme, panels and dialogs instead of cards

- **Status:** 🟢 User decisions 2026-09-13 (ADR D20, D21, D22). Where this section and §4 differ, this
  section wins; §4's places, surfaces and contribution mechanism stay, only their **rendering**
  changes.
- **The desktop contract** is `ui-presentation-rule.md`: its principles (§2) and its clauses for
  menus, toolbars, dialogs, panels, tables, feedback and keyboard, each citing its source in the
  Microsoft, KDE, Apple and GNOME desktop guidance (`EPIC-033A`). Every row below names the
  principle it serves.

## 11.1 The decision and its reasons (recorded so it is not reversed a fourth time)

This is the third change of UI toolkit in this repository's history (QML → QtWidgets in
`EPIC-005`/`EPIC-006`, QtWidgets → per-widget QML in `EPIC-015`, and now QtWidgets only). The
reasons, measured on 2026-09-13:

1. The desktop conventions the user wants — menu bar, toolbars, status bar, dialogs, keyboard
   shortcuts, undo — are what `QMainWindow`, `QAction`, `QDialog` and `QUndoStack` provide
   natively; QML islands embedded in QtWidgets have to re-create them. Today exactly **one** file
   in the app uses any of them.
2. Every QML island is its own `QQmlEngine` inside a `QQuickWidget` (`create_quick_widget()`),
   which produced `BUG-115` (black backgrounds) and makes a workbench of dock panels awkward.
3. The app uses **none** of the Engine's QML kit (`import Sagittarius.UI`: zero hits), and the
   app's own token/theme layer (`kit/style.py`, `qdarktheme`, `seed_app_theme`) is, in the user's
   words, *"rất tệ"* ("very bad") — it is retired rather than ported.

What is kept from the Engine's `pyside_mvc`: `BaseView`, `BasePresenter`, `PresenterManager`,
`QtEventBridge`, the thread-affinity safety helpers — the parts that are toolkit-agnostic. What
is no longer used by this app: `create_quick_widget`, `configure_app_qml`, the tokens, the QML
kit.

## 11.2 The information architecture: modes, panels, menus and commands

**Status:** approved by the user on 2026-10-04 (`EPIC-033O`, `DECISION_2026-10-04_windows_workbench.md`
D10); the modes are built by `EPIC-033H`–`033L` and `033P`.

The shape is designed from what a person does (`Docs/SPEC/`), not from the screens that grew one
feature at a time. One **mode** per job; inside it, the panels that job needs; everything else one
menu away (KDE "simple by default, powerful when needed"; MS "focus on what is likely"). Each mode
is a workbench host — a `QMainWindow` with a central widget, docks and toolbars, and a perspective
saved per mode (Qt Creator's shape; MetaTrader 5 and TWS are workbenches of dockable panels
around a chart).

### 11.2.1 Modes

| Mode (shortcut) | The job | SPECs | Central widget | Default panels |
| :--- | :--- | :--- | :--- | :--- |
| **Market** (Ctrl+1) | watch the live market | SPEC-002, SPEC-003 | chart, one tab per open symbol | right: Watchlist, Indicators (tabbed); bottom: Output (hidden) |
| **Trade** (Ctrl+2) | trade one venue by hand and see the account | SPEC-004, 005, 006, 007, 012, 013 | chart of the traded symbol | right: Order entry, Account summary; bottom: Positions (Futures) or Assets (Spot), Open orders, Order history, Trade history, Equity (tabbed) |
| **Bots** (Ctrl+3) | create, judge, run and watch automated trading | SPEC-014, SPEC-010 | the selected bot's chart (its levels, fills and price; `EPIC-029` D16) | left: Bots (the list); right: Plan (the kind's panel: parameters and verdicts); bottom: Orders, Fills, Log (tabbed) |
| **Backtest** (Ctrl+4) | test a strategy on stored history | SPEC-009 | result chart | left: Run setup; right: Metrics; bottom: Trades, Monte Carlo (tabbed) |
| **Data** (Ctrl+5) | keep history complete | SPEC-001, SPEC-008 | coverage table (symbol × timeframe) | bottom: Gaps, Output |
| **Developer** (Ctrl+6, developer mode only) | look inside the running app | SPEC-011 (developer part) | event log | right: probes |

**Bots replaces a Strategies mode** (`EPIC-029`: the user asked for "a **Bots** tab", judged the
six signal strategies "junk", put signal bots and DCA last, and wants the desks "manual only, with
a takeover from a bot"). A strategy armed on a venue (SPEC-010) is listed in the Bots mode as
its own row until `EPIC-029L` makes it a signal-bot kind; Trade stays manual. Each bot kind
contributes its panel and its toolbar (`kind_panels`, SPEC-014: "each bot type has its own
toolbar"); the kind's toolbar shows while a bot of that kind is selected and its commands stay in
the Bots menu, disabled otherwise.

Futures and Spot are one Trade mode with a venue selector, not two screens: the job is the same,
only the account panel differs (`EPIC-027O` already switches it once by market). The app opens on
the mode the user last used; there is no Welcome page.

### 11.2.2 Always visible

- **Emergency stop** is an action on every mode's toolbar and in the Trade menu (SPEC-007): the
  one command that must never be a menu away.
- **The venue in text** — "Binance Futures Testnet", "Binance Spot Live" — in the window title and
  the status bar, never by colour alone (MS `vis-color`; replaces the coloured banner of
  `EPIC-021K`; `test_environment_banner_all_screens.py` is retargeted to the title).
- **The connection state** in the status bar, as a word plus an icon (SPEC-003).

### 11.2.3 The menu bar is the catalogue of commands

Sentence case; `&` marks the access key, unique among the menu-bar titles (F, E, V, R, B, D, T, W, H, and P for Developer) and within each menu; "…" only where the command asks for more input;
"confirm" means a dialog with specific verbs and the safe choice as default
(`ui-presentation-rule.md` §10). A command with a toolbar column is also on that mode's toolbar.

| Menu | Command | Shortcut | Toolbar | Confirm |
| :--- | :--- | :--- | :--- | :-: |
| &File | &Export table… | — | — | — |
| | &Close chart (Market: the chart tab in front) | `QKeySequence.Close` (Ctrl+F4, Ctrl+W) | — | — |
| | E&xit | Alt+F4 | — | — |
| &Edit | &Copy | Ctrl+C | — | — |
| | Select &all | Ctrl+A | — | — |
| | &Find… | Ctrl+F | — | — |
| &View | &Market, T&rade, &Bots, Back&test, &Data, De&veloper (one checkable action per mode) | Ctrl+1 … Ctrl+6 | mode selector | — |
| | one toggle per panel of the current mode, access keys assigned per mode (`EPIC-033D` checks them) | — | — | — |
| | T&oolbars ›, Stat&us bar | — | — | — |
| | &Full screen | F11 | — | — |
| T&rade | &Venue › Futures, Spot | — | Trade | — |
| | &Enable live trading (checkable) | — | Trade | on enable |
| | &New order… | F9 | Trade | on place |
| | Cancel &order | Del | — | yes |
| | Cancel a&ll orders | — | Trade | yes |
| | Emergency &stop | F8 | every mode | yes |
| &Bots | &New bot… | — | Bots | — |
| | &Save bot | Ctrl+S | Bots | — |
| | S&tart | — | Bots | — |
| | &Pause / &Resume | — | Bots | — |
| | &Confirm resume | — | Bots | yes |
| | St&op… | — | Bots | yes (the base asset: keep, preselected; `EPIC-029` O3) |
| | &Delete bot… | — | — | yes |
| | the selected kind's commands (Spot grid: Suggest from &ATR, Suggest from Bollin&ger, &Fit levels) | — | the kind's toolbar | — |
| &Data | &Sync history… | Ctrl+L | Data | — |
| | &Check gaps | — | Data | — |
| | &Repair gap, Repair a&ll gaps | — | Data (Repair gap) | — |
| | &Inspect candles | — | — | — |
| | St&op (while a task runs) | — | Data | — |
| | Scan s&tatus, Scan &all shards, Sync all &gaps | — | Data (Scan status) | — |
| | &Export data…, I&mport data…, Optimi&ze database | — | — | — |
| | &Delete data, &Purge all data | — | — | yes |
| &Tools | &Run backtest… | F7 | Backtest | — |
| | &Stop backtest | — | Backtest | — |
| | Check &connection | — | — | — |
| | &Options | `QKeySequence.Preferences` | — | — |
| &Window | &Reset layout | — | — | — |
| | &Output | Ctrl+J | — | — |
| &Help | &Documentation | F1 | — | — |
| | &Keyboard shortcuts | — | — | — |
| | &About Sagittarius Elite Warrior | — | — | — |

**Until the mode tasks land** (`EPIC-033D` converted the screens as they are; `EPIC-033H`–`033L` and `033P` rebuild them to the table above):

- The table's menus, names and shortcuts hold where a screen already has the command: Trade's Enable live trading, Emergency stop (F8) and New order… (F9); Bots' New bot…, Save bot (Ctrl+S), Start, Pause, Resume, Confirm resume and Stop…; Tools' Run backtest (F7) and Stop backtest.
- Delete bot carries no "…": it only confirms, and "…" marks a command that asks for more input (§4 of the rule).
- Emergency stop is on each desk's toolbar, for that desk's venue, not on every mode's: one Emergency stop for every venue comes with the single Trade mode (`EPIC-033I`).
- The current screens also contribute commands the table does not list yet, each in its module's menu and scoped to its mode:
  - Trade, on the Dev Board: Load history, Start live, Stop live (`EPIC-033P`).
  - Tools, in Backtest: Save report…, Import report…, Compare reports…, In-sample vs out-of-sample, Monte Carlo (`EPIC-033L`).
  - Bots: Refresh fills (`EPIC-033K`).

Run backtest is F7, not Ctrl+R: GNOME and XFCE reserve Ctrl+R for Refresh, and the Engine's shortcut policy refuses it. In View, the modes are &Bots and Back&test, not B&ots and &Backtest, because T&oolbars in the same menu already uses O.

Developer mode adds a `Develo&per` menu before Tools, holding the probes. Context menus on tables
repeat the menu commands that act on the selected row (Cancel order, Copy).

### 11.2.4 Today's screens, mapped

| Today | Becomes | Why |
| :--- | :--- | :--- |
| Welcome | dropped | the app opens on the last mode; developer mode is a page in Options |
| Dev Board | Market (chart, watchlist, indicators) and Developer (probes); its order dialog becomes Trade's New order | it held three jobs |
| Watchlist screen | the Watchlist panel in Market | a list beside the chart, not a place of its own |
| Futures desk, Spot desk | Trade, with the venue selector | one job, two venues |
| Backtest | Backtest | its overlays and nested scrolling become panels |
| Bots tab (`bots`, `EPIC-029F`) | Bots | already one job; its list, plan and Orders/Fills/Log become docks and its buttons become actions |
| the desks' strategy cards | a row per venue in Bots | a strategy runs unattended, which is what a bot is |
| Data Management | Data | — |
| Settings route | Tools → Options dialog | settings are a dialog on every desktop platform |

### 11.2.5 How the extension places render

The mechanism of §4 is unchanged: a module contributes to places, the host renders them.

| Place (§4.6, vocabulary §2) | Rendered as | Principle served |
| :--- | :--- | :--- |
| `SCREEN` | a **mode**; a `QMainWindow` in the stacked widget, its perspective saved and restored per user | Familiarity, Remember the user |
| `HEADER` | a `QToolBar` of `QAction`s — one action carries its menu entry, toolbar button, shortcut and enabled state | Consistency |
| `CONTEXT_BAR` | a second toolbar (symbol, timeframe, venue) | Simple by default |
| `WORKSPACE` | the mode's central widget | Familiarity |
| `RAIL` | `QDockWidget`s — **panels** the user can move, tab, float and hide; the layout persists | Remember the user |
| `CONSOLE` | the one Output dock in the bottom area (`EPIC-033F`) | Familiarity |
| `MODAL` | a `QDialog` with a `QDialogButtonBox`, a title naming the command, validation before OK enables | Prevention over confirmation |
| `STATUS_TILE` | a widget in the `QStatusBar` (connection, venue, run progress) | Actionable errors |
| *(not a place)* an Options page (`contribute_options_page`, `EPIC-033E`) | a page in Tools → **Options** (sections left, pages right, OK / Cancel / Apply) | Familiarity |
| `DEV_PROBE` | a `QDockWidget` in the Developer mode, only under `dev.mode` | — |

The surface host implements `IPlaceHost` with a `QMainWindow`; `PageShell` is retired. The
`order` field becomes the initial dock order; after that the user's saved perspective wins.

## 11.3 Panels and dialogs replace cards

The old "card" (`kit.Card`: a titled box in a scrolling column) is retired; the user's judgement
(*"các card cũ cũng rất là tệ"*) matches the precedent — no professional trading desktop stacks
cards. Two things replace it:

- A **panel** is a `QDockWidget` whose content is a module-owned widget: a table (`QTableView` on
  a model), a form, or a read-only summary. It has a title, a close button, and nothing else of its
  own. One panel = one factory in `module.contribute()`; the module's `ui/panels/` package holds it.
- A **dialog** is the desktop way to *do* something that needs input and confirmation: place a
  manual order on Dev Board (shortcut F9, as in MT5, also reachable from a toolbar action; the
  desks keep their order panel in the rail, where it is the screen's purpose — `EPIC-028`),
  arm a strategy with parameters, pick a time range, edit settings. Every dialog has Cancel, states
  what OK will do, validates before enabling OK, and reports the result in the status bar.

Which former widgets become what:

| Former | Now | Where |
| :--- | :--- | :--- |
| positions table, open orders table (QML tables) | panels (`QTableView` + `QAbstractTableModel`; the existing view models keep their role) | `trading/ui/panels/` |
| session card | a status-bar tile (enabled / orders this session) plus the Enable / Disable / Emergency-stop actions on the toolbar; one `DeskSessionControls` behind every screen's actions, each for one venue (`EPIC-028M`) | `trading/ui/` |
| manual order card | the desks' **order panel** (`trading/ui/desk/order_entry/`): in each desk's rail, and in Dev Board's **Order** dialog (F9) for the venue the board trades | `EPIC-028H`/`028I`; the card left in `EPIC-028M` |
| equity chart | a panel hosting the chart widget | `trading/ui/panels/` |
| strategy card, last-signal card | the Strategy panel (armed strategy, parameters button, last signal) | `strategy/ui/panels/` |
| strategy parameters dialog | a `QDialog` | `strategy/ui/dialogs/` |
| Dev Board system controls | a toolbar of actions | `market_data/ui/` |
| indicator checklist | the Market mode's Indicators panel | `trading/ui/market/` (`EPIC-033H`): the mode also runs SPEC-003's check through `trading`'s account port, and `market_data` may not depend on `trading` |
| backtest modals (11, QML) | `QDialog`s | `backtesting/ui/dialogs/` |
| Data Management tables, time-range and timeframe pickers | panels and dialogs | `market_data/ui/` |
| Welcome | a mode with a central widget only: name, version, Start, developer-mode switch | shell |
| Bots tab (new, `EPIC-029F`) | a mode: the list of bots (`QTableView`) beside the detail shell; New bot, Stop and Delete are `QDialog`/`QMessageBox` questions with the action named on the button and Cancel as the safe answer; every action is disabled with its reason as a tooltip while it is not legal or while another runs | `bots/ui/bots_screen/` |

## 11.4 Theme: the OS default, nothing else — reached as a ratchet

The target is unchanged: the app applies **no** stylesheet, palette, token set or third-party
theme. Widgets look like the platform's widgets (Windows, macOS, a Linux desktop) — that is the
familiarity principle. A colour is used only where it carries meaning (profit / loss, connection
state), through `QPalette` roles or a per-widget property, never a global stylesheet. A designed
theme is a later decision, explicitly deferred by the user (*"sau này design màu theme tính sau"*).

**How it is reached** (revised 2026-09-13 while executing PR 0.2; the earlier text said
`seed_app_theme()` and `kit/style.py` are deleted in Phase 0, which is not possible — see below).

| Step | Phase | What happens |
| :--- | :-: | :--- |
| The global sheet goes | **0** (PR 0.2) | `qdarktheme` is removed from `requirements.txt` and from the dependency preflight; `app_bootstrapper._apply_theme()` is deleted with the two `ui.theme.*` config keys it read. Standard controls — menus, dialogs, scrollbars, combo popups, tooltips — render in the platform's theme from this point on. `test_no_global_stylesheet.py` forbids any theme distribution and any `setStyleSheet` on the application, for good |
| Per-widget styling shrinks | 0 → 4 | every phase rebuilds its screens as plain QtWidgets panels and takes its styling with it. `tools/measure_app_styling.py` counts what is left and `test_app_styling_only_shrinks.py` holds the ground: the four numbers may only fall, and a phase that lowers one must lower the baseline in the same commit |
| The colour source goes | **4** | `Palette`, `kit/style.py`, `seed_app_theme()` and the palette guard are deleted together with the last `.qml` file and the last `kit/` widget, when nothing reads them. **Half of that condition is met:** `EPIC-025` PR 4.3l deleted the last `.qml` under `src/` (`qml_files` and `qml_theme_refs` are both **0**), so what still holds the colour source up is the `kit/` widgets — PR 4.4's |

**Why the middle row exists.** Two facts measured on the tree in PR 0.2 make a Phase 0 deletion
impossible rather than merely expensive. First, the Engine's `create_quick_widget()` **raises**
without `configure_app_qml()` (`BOT-132`), and `configure_app_qml()` is fed by `Palette`; the 35
surviving `.qml` files carry 229 `Theme.*` bindings, so deleting the palette in Phase 0 would stop
Trading, Dev Board and Backtest from opening at all. Second, `kit/style.py` is called from 52
`apply_role()` sites across 26 files, beside 151 direct `setStyleSheet()` calls in 22 files;
deleting it in Phase 0 means restyling every screen that Phases 1–4 are going to rebuild anyway —
Phase 4's work done in Phase 0, against the Strangler Fig rule that the application keeps running
at every step (§6.3). The ratchet reaches the same end state, in the order the migration already
follows, and makes each phase's share visible as a number.

## 11.5 Rules that follow, and what enforces them

The rules are `ui-presentation-rule.md`'s; this section records only how the booted app is held to
them, since this list once said "enforced" where no test existed.

- **Static bans**, per line of code: `tests/unit/architecture/test_stock_controls_only.py` counts
  style sheets, hand-set sizes, per-view item-view configuration, font families, colour literals and
  checkable push buttons; every count only falls and reaches zero when `EPIC-033M` closes.
- **The composed window**, per mode: `tests/integration/presentation/ui/test_workbench_conformance.py`
  boots the app and checks the menu-bar order, the system font, that each mode is a workbench host,
  that every dock has a View toggle, no style sheet, control heights at their size hint, no nested
  scrolling, toolbars of actions only, item-view conventions, escaped ampersands and the perspective
  round trip. Its baseline lists today's failures per mode and only shrinks.
- **No `.qml`**: `test_no_new_qml.py` is a ban; `src/` holds none.
- What no test sees — confirmation wording, error text, tab order — is a review row (`H3`, `H7`).

## 11.6 What this changes in the plan

- Phase 0 (`EPIC-025A`) rebuilds Data Management's four QML widgets as panels and dialogs and
  removes the theme layer; Phase 1 rebuilds Trading and Dev Board as modes with docks and the Order
  dialog; Phase 3 rebuilds the eleven backtest modals as dialogs; Phase 4 deletes what is left of
  `kit/` and `qml/`. The Gantt bars are re-cut accordingly.
- The Engine track: `TASK-043` item 3 (QML import paths) is dropped; E2's region host is a
  `QMainWindow`-based surface host; the Engine's tokens and QML kit are not consumed by this app.
  Whether the Engine grows a QtWidgets kit is an Engine decision the user has deferred.
