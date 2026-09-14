# §11 — The desktop workbench: QtWidgets only, the OS theme, panels and dialogs instead of cards

- **Status:** 🟢 User decisions 2026-09-13 (ADR D20, D21, D22). Where this section and §4 differ, this
  section wins; §4's places, surfaces and contribution mechanism stay, only their **rendering**
  changes.
- **The user's UX principles**, quoted in full in `ui-presentation-rule.md` ("Desktop UX
  principles"): familiarity, consistency, efficiency, clarity, user control, robustness,
  scalability. Every row below names the principle it serves.

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

## 11.2 The workbench is `QMainWindow` — the places map onto its parts

"Apply before you invent": MetaTrader 5 and Interactive Brokers TWS are both workbenches of
dockable panels around a central chart, with order entry in a **dialog** (MT5: F9 "New Order")
or a dedicated window; Qt Creator has **modes** (Welcome / Edit / Debug) with a saved
**perspective** each (`QMainWindow.saveState()` / `restoreState()`). The app follows that shape.

| Place (§4.6, vocabulary §2) | Rendered as | Principle served |
| :--- | :--- | :--- |
| `SCREEN` | a **mode** in the mode selector (the sidebar); each mode is a `QMainWindow` nested in the stacked widget, with its own perspective saved and restored per user | Familiarity, User control |
| `HEADER` | a `QToolBar` of `QAction`s — one action carries its menu entry, toolbar button, shortcut and enabled state in one object | Consistency, Efficiency |
| `CONTEXT_BAR` | a second toolbar (symbol, timeframe, connection) | Efficiency |
| `WORKSPACE` | the mode's central widget (the chart; several charts as tabs or an MDI area on Dev Board) | Clarity |
| `RAIL` | `QDockWidget`s in the right dock area — **panels** (positions, open orders, session, strategy, last signal); the user can move, tab, float, hide them; layout persists | User control, Scalability |
| `CONSOLE` | a `QDockWidget` in the bottom dock area | Clarity |
| `MODAL` | a `QDialog` with explicit OK/Cancel, a title that names the action, and validation before OK enables | Clarity, User control |
| `STATUS_TILE` | a widget in the `QStatusBar` (websocket pill, price ticker, run progress) | Clarity |
| `SETTINGS_SECTION` | a page in one Settings **dialog** (list of sections on the left, stacked pages on the right — Qt Creator's Options dialog), with Apply / Cancel | Familiarity, User control |
| `DEV_PROBE` | a `QDockWidget` in Dev Board's dock area, only under `dev.mode` | — |

Consequences for the mechanism (§4.3, SDD): nothing in the descriptor changes; `factory` still
returns a `QWidget`. The surface host implements `IPlaceHost` with a `QMainWindow` instead of
`PageShell`; `PageShell` is retired. The `order` field becomes the initial dock order; after that
the user's saved perspective wins ("regions decide geometry" now means "the user decides").

## 11.3 Panels and dialogs replace cards

The old "card" (`kit.Card`: a titled box in a scrolling column) is retired; the user's judgement
(*"các card cũ cũng rất là tệ"*) matches the precedent — no professional trading desktop stacks
cards. Two things replace it:

- A **panel** is a `QDockWidget` whose content is a module-owned widget: a table (`QTableView` on
  a model), a form, or a read-only summary. It has a title, a close button, and nothing else of its
  own. One panel = one factory in `module.contribute()`; the module's `ui/panels/` package holds it.
- A **dialog** is the desktop way to *do* something that needs input and confirmation: place a
  manual order (shortcut F9, as in MT5 — and on Dev Board also reachable from a toolbar action),
  arm a strategy with parameters, pick a time range, edit settings. Every dialog has Cancel, states
  what OK will do, validates before enabling OK, and reports the result in the status bar.

Which former widgets become what:

| Former | Now | Where |
| :--- | :--- | :--- |
| positions table, open orders table (QML tables) | panels (`QTableView` + `QAbstractTableModel`; the existing view models keep their role) | `trading/ui/panels/` |
| session card | a status-bar tile (enabled / orders this session) plus the Enable / Disable / Emergency-stop actions on the toolbar | `trading/ui/` |
| manual order card | the **Order** dialog (F9) | `trading/ui/dialogs/` — Dev Board only (ADR D15), one line to add the action to Trading later |
| equity chart | a panel hosting the chart widget | `trading/ui/panels/` |
| strategy card, last-signal card | the Strategy panel (armed strategy, parameters button, last signal) | `strategy/ui/panels/` |
| strategy parameters dialog | a `QDialog` | `strategy/ui/dialogs/` |
| Dev Board system controls | a toolbar of actions | `market_data/ui/` |
| indicator checklist | a panel | `market_data/ui/panels/` (support widget contributed by the module that wants it) |
| backtest modals (11, QML) | `QDialog`s | `backtesting/ui/dialogs/` |
| Data Management tables, time-range and timeframe pickers | panels and dialogs | `market_data/ui/` |
| Welcome | a mode with a central widget only: name, version, Start, developer-mode switch | shell |

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
| The colour source goes | **4** | `Palette`, `kit/style.py`, `seed_app_theme()` and the palette guard are deleted together with the last `.qml` file and the last `kit/` widget, when nothing reads them |

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

## 11.5 Rules that follow, enforced

- **One `QAction` per user action**, registered once in the module's contribution and reused by
  menu, toolbar and shortcut; a guard fails on a `QPushButton` that triggers a command a `QAction`
  also triggers.
- **Every long operation shows progress and stays cancellable** (`QProgressBar` in the status bar
  or the panel; the existing `ActionOwnershipTracker` and cancellation tokens do the work). The UI
  thread is never blocked — the existing `async-ui-action-rule.md` is unchanged.
- **Every destructive or money-moving action confirms in a dialog** that names the consequence
  (Emergency stop, Purge vault, Place order).
- **Perspectives persist per mode** (`saveState` keyed by mode id and app version); "Reset layout"
  is a menu action.
- **No new `.qml` file** (a guard: `find src -name '*.qml'` must not grow, and reaches zero in
  Phase 4). `qml-rule.md` is historical.

## 11.6 What this changes in the plan

- Phase 0 (`EPIC-025A`) rebuilds Data Management's four QML widgets as panels and dialogs and
  removes the theme layer; Phase 1 rebuilds Trading and Dev Board as modes with docks and the Order
  dialog; Phase 3 rebuilds the eleven backtest modals as dialogs; Phase 4 deletes what is left of
  `kit/` and `qml/`. The Gantt bars are re-cut accordingly.
- The Engine track: `TASK-043` item 3 (QML import paths) is dropped; E2's region host is a
  `QMainWindow`-based surface host; the Engine's tokens and QML kit are not consumed by this app.
  Whether the Engine grows a QtWidgets kit is an Engine decision the user has deferred.
