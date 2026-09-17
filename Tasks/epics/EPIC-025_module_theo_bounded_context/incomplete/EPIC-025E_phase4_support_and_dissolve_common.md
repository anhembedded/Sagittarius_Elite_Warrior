# EPIC-025E — Phase 4: `support/{charting, indicators, ui_kit}`; dissolve `presentation/ui/common/`

- **Status:** 🟡 In progress — §3 is the measured cut, taken 2026-09-16 after Phase 3 closed its coded work
- **Repository:** Elite
- **Blocked by:** D · **Blocks:** F
- **Read first:** HLD §2.3 (a support package is not a bounded context: no business language, no
  business rules allowed), §3.4; ADR D6 (the per-module QML question is reopened here).

## 1. What to do

1. ✅ **Done, PR 1.6f** (pulled forward for the same reason as step 3). `support/charting/` ←
   `components/chart_card` (27 files, QtWidgets permanently), `components/timeframe_picker` and
   the QML `TimeframePicker`, plus `InfoField` in `contracts/` — split out of
   `domain/indicator_scripts/base_indicator_script.py`, which re-exports it, because it was the
   single legacy import keeping the package in. `IChartHost` and the marker/region types are
   **not** published yet: their consumer is Phase 3's backtesting, and `backtest_chart_host.py`
   still lives beside the backtest screen. What 1.6f *did* settle is the boundary question the
   extraction raised — HLD §6.1 now lets the two UI support packages import each other whole,
   measured and pinned, rather than routing 20 imports through an ABC façade written for one
   consumer.
2. ✅ **Done, PR 1.6g** (pulled forward like steps 1 and 3). `support/indicators/` ←
   `domain/{indicators,indicator_scripts,scripting}`, `application/services/
   indicator_script_registry.py` and `components/indicator_scripts` (as `ui/`) — 26 files,
   measured clean before the move: the only external imports were `core.vo` and
   `support/charting/contracts`, both permitted. `IIndicatorCatalog` is **not** published yet;
   its consumers are Phase 2's `strategy` and Phase 3's backtesting, both still in the legacy
   tree, and a port with no caller outside its own package is a seam invented ahead of its
   need.

   **`components/strategy_params` did not come, and the reason belongs in the design rather
   than in a to-do list.** §3.5 assigns it here, but `bot_params_form.py` imports
   `BaseStrategy` from `domain/strategies` — Phase 2's `modules/strategy`. So the assignment
   cannot be satisfied before that module exists, and it is not obvious it should be: a form
   that renders *a strategy's* parameters reads more like `modules/strategy/ui` than like a
   generic indicators package. ~~**Open for the user**~~ — **answered by PR 2.1e, see §3.4**: it went
   to `modules/strategy/ui`, and `support/indicators` was never satisfiable because §6.1 forbids a
   support package importing a module at all.
3. `support/ui_kit/` ← what survives of `kit/` after HLD §11 (no `PageShell`, no `style.py`, no
   tokens, no `qml/`): the generic QtWidgets helpers (`binding`, `widget_value`, guards) and the
   five genuinely shared items of `ui/common` (`action_ownership_tracker`, `app_defaults`,
   `base_feed`, `sync_progress_*`). `src/presentation/ui/qml/` is **deleted**; `find src -name
   '*.qml'` returns 0.
   **Started early, in Phase 1, and not as a shortcut.** Phase 1 closed measuring that its own
   last criterion — the two screens into `modules/trading/ui/`, and with them the 59 duplicated
   members — cannot be met until this package exists, and Phase 2's strategy cards sit behind
   the same wall. So the package is being built **bottom-up from Phase 1 onward**, one clean
   leaf per pull request, each one costing zero allowlist entries because a legacy file may
   import `support/**` whole. Done so far: `assets/` (PR 1.6a), `kit/` (PR 1.6b, 28
   files), six `ui/common` helpers (PR 1.6c) and `constants.py` + `state/` +
   `registry/` + `sidebar/` + `symbol_picker/` + `app_log_panel.py` (PR 1.6d).
   **1.6d also retired four of the nine lines in
   `baseline_shell_legacy_imports.txt` — the `registry` ones, which this file had
   scheduled for Phase 5.** Not the way it expected: the plan was the Engine's
   `NavigationService` replacing `ScreenRegistry`; what retired them is the
   registry moving into `support/`, after which `shell -> support/**` is
   permitted outright and needs no recorded permission.

   What is left of this step, re-measured after 1.6d: `components/environment_banner`
   (3 files) is a leaf **except** for `domain.value_objects.venue_alignment`, and
   `support/*` may not import the legacy tree at all — HLD §02's own row already
   assigns `VenueAlignment` to `support/binance_gateway/contracts`, and its only
   imports are already from there, so that move unblocks it.
   `components/market_picker` (3) waits on `qml/SelectList`, which this phase
   deletes rather than moves, and the same argument applies to `qml/kit` (13) and
   `qml/DataTable` (5) — moving something ADR D21 deletes in this phase is work
   done twice. Then `services/display_timezone_service.py`.

   **`sync_progress_*` is no longer part of this step, and the reason is a conflict
   between two clauses of the HLD rather than a measurement that changed.** §3.5
   assigned `sync_progress_{feed,report}` to `support/ui_kit`; `sync_progress_feed`
   reads `modules.market_data.contracts.events.sync_events`, and §6.1's
   `support/* → modules/*` prohibition has **no** contracts exception — driving that
   pair through `boundaries/rules.py::import_is_allowed` returns `False`, so this is
   the rule table refusing it, not an allowlist entry waiting to be written. A feed
   whose whole job is to normalise *one module's* events is that module's UI, so the
   destination should be `modules/market_data/ui/`. That re-assignment changes what
   the epic promised, so it was left **open**. — **Closed in §3.3, and by a rule rather than a
   preference:** `support/ui_kit` is refused by the rule table, so `modules/market_data/ui/` is the
   only destination that does not require changing a rule the user already has. It goes as PR 4.2a. What remains for *this* phase is whatever still has a legacy
   import when Phase 3 ends, plus the deletions in step 4, which only this phase can do.
4. **Delete** `ui/common/`; **delete** `binance_bot_module.py` (now empty); the `settings` screen
   becomes a surface that hangs each module's `settings_section` contribution.

   **This phase now also owns the epic's "59 duplicated members → 0" criterion**, by user
   decision 2026-09-16
   ([`DECISION_2026-09-16`](../DECISION_2026-09-16_the_duplication_criterion_waits.md)). It was
   Phase 1's exit gate; after PRs 1.6a–1.6g the two screens' remaining legacy imports measured 42,
   and 11 of them had no destination that exists yet — six QML packages **this phase deletes**
   (ADR D20–D21) and five needing Phase 2's `modules/strategy`. Moving the screens early would
   have meant writing those 11 into a shrink-only allowlist, so the criterion travels with the
   deletions in this step instead. **§3.1 revises the assumption underneath that decision:** it took the two screens as travelling
   together, both waiting on the QML; measured, only `screens/dashboard` does (four QML imports),
   while `screens/trading`'s thirteen blockers are all `trading`'s own code, so the pair splits and
   the criterion starts falling at PR 4.1c rather than after the deletions. Concretely: once
   step 3 has emptied `ui/common` and the QML packages are gone, `screens/trading` and
   `screens/dashboard` `git mv` into
   `modules/trading/ui/` with the remaining imports pointing at `support/**` and
   `modules/*/contracts` only, and `tools/measure_duplicate_members.py` is expected to report
   **0** — which is also the last thing `test_presenter_duplication_only_shrinks.py` has to
   ratchet.
5. (ADR D6 is superseded by D20 — there is no QML to place.)
6. **Inherited from Phase 0** (`EPIC-025A` §1.8, deferred 2026-09-14): `git mv` the rebuilt Data
   Management screen into `modules/market_data/ui/`, have `MarketDataModule.contribute()` offer it
   as a `ScreenContribution`, and remove `DatabaseScreenModule` from `LEGACY_SCREEN_MODULES`. PR
   0.4b rebuilt the screen on QtWidgets but left it where it was: the move needed 35 imports from
   `modules/market_data/ui/` back into `presentation.ui.{kit,assets,common,components,state,qml}`,
   and steps 1–4 above are what those imports are waiting for. It is the first check that
   `_UI_SUPPORT_ZONES` (a module's `ui/` may import `support/ui_kit` and `support/charting` whole)
   is enough — if a 36th import has no home in `support/`, that is the finding.

## 2. Done when

- `ls src/presentation/ui/common` → does not exist; the guard allowlist is **empty**; the two
  layer violations (screens importing `infrastructure/`) are gone.

---

## 3. The cut, measured 2026-09-16 before any code moved

Phase 3's §4 is the template: measure every remaining group's imports of the legacy tree *first*,
because that number is what says which pull request can exist and in what order. Item counts are
`.py` files, `__pycache__` excluded; the imports counted are those naming
`presentation`, `domain`, `application`, `infrastructure` or `binance_bot_module` from **outside**
the group's own package.

| Group | Files | Legacy imports | What they are |
| :--- | :-: | :-: | :--- |
| `ui/components/order_book` | 7 | **0** | — it is a **clean leaf**, exactly `assets/`'s position in PR 1.6a |
| `ui/components` (root: `__init__`, `critical_error_dialog`) | 2 | **0** | — |
| `ui/qml` | 68 (+24 `.qml`) | **0** | — the leaf this phase **deletes** rather than moves (ADR D20–D21) |
| `screens/settings` | 6 | **1** | `presentation.cli.exchange_status_formatter` |
| `ui/components/market_picker` | 3 | **2** | both `qml/SelectList` |
| `ui/common` | 13 | **2** | both `components/order_book` |
| `screens/data_management` | 23 | **6** | 3 `sync_progress_*`, `qml_property`, `qml/kit`, `qml/TimeRangePicker` |
| `screens/trading` | 9 | **13** | 6 `order_book`, 7 `ui/common` — **and all thirteen are `trading`'s own code** |
| `screens/dashboard` | 15 | **20** | 4 `order_book`, 8 `ui/common`, 4 QML (`SymbolPicker` ×2, `kit` ×2), 4 others |
| `screens/backtest` | 74 | **33** | **28 of them QML**, which is `EPIC-025D` §4.1's finding restated |

### 3.1 The finding: `screens/trading` is three pull requests from moving, and none of them is hard

Its thirteen blockers are **six** `order_book` imports and **seven** `ui/common` feeds, and every
one of those thirteen names code that HLD §3.5 already assigns to `modules/trading`:
`equity_chart_adapter`, `equity_feed`, `execute_order_block_reason`, `live_order_book_coordinator`,
`market_tick_feed`, `order_feed`, `order_fill_marker`. Nothing it needs is QML, and nothing it needs
belongs to another context. So the epic's *"59 duplicated members → 0"* criterion — Phase 1's exit
gate, handed to this phase by the user's `DECISION_2026-09-16` — is reachable **before** the QML
deletions, which is not what that decision assumed. It assumed the two screens travel together and
both wait on the QML; measured, only `screens/dashboard` does (four QML imports), and the pair can be
split.

### 3.2 The pull requests, in the order the measurement dictates

| PR | What | Why it can go now |
| :--- | :--- | :--- |
| **4.1a** | the six `trading`-owned `ui/common` feeds → `modules/trading/ui/` — `equity_chart_adapter`, `equity_feed`, `execute_order_block_reason`, `market_tick_feed`, `order_feed`, `order_fill_marker` | each has **0** legacy imports. The seventh, `live_order_book_coordinator`, reads `order_book` and travels with it in 4.1b |
| **4.1b** | `components/order_book` (7 files) → `modules/trading/ui/` **together with** `screens/data_management`'s table models → `modules/market_data/ui/`, extracting the shared `RowTableModel` into `support/ui_kit` in the same pull request; `live_order_book_coordinator` comes too | §3.5: `order_book` is a clean leaf on its own, but moving it alone raises the duplication ratchet, and the user's decision of 2026-09-16 is to do the extraction **once**, when both packages move, rather than churning these files twice |
| ~~4.1c~~ ❌ | `screens/trading` → `modules/trading/ui/` — **folded into 4.4, §3.11.** Its legacy-import count did reach **0**, and that turned out not to be the binding constraint: merging it into the existing `trading.ui` package deduplicates nothing (the total stays at 112) while making `phase_1_count` read a false **0**, and re-keying the metric honestly would raise its ratchet 32 → 39, which `ci-rule` §5.5 forbids. The two live screens travel together after the deletions, as the user's `DECISION_2026-09-16` said | — |
| ~~4.2a~~ ❌ | `sync_progress_{feed,report}` → `modules/market_data/ui/`, with `symbol_options_coordinator`; `base_event_logger` → `modules/backtesting/ui/` — **folded into 4.4, §3.12.** Measured at PR review time (2026-09-17): moving these four alone costs the boundary allowlist 58 → 68 (10 new lines across 7 legacy consumer files), which the rewritten `architecture-rule.md` now forbids outright. Worse than a ratchet problem: every one of those 7 consumers is itself moving in 4.2b or 4.4, so the only zero-cost sequencing is moving each leaf file in the same pull request as **all** of its consumers — which for `sync_progress_{feed,report}` means 4.2b and 4.4 at once, since `data_management` (4.2b) and `backtest`/`dashboard` (4.4) both import them | — |
| ~~4.2b~~ ❌ | `screens/data_management` → `modules/market_data/ui/` (step 6, inherited from Phase 0) — **folded into 4.4, §3.12**, for the same reason as 4.2a: after 4.1b its only remaining blockers are QML (so it already waited on 4.3, same as 4.4) and the four leaf files 4.2a would have moved, which it shares consumers with across 4.4's screens too | — |
| **4.3** | the QML deletions (ADR D20–D21), in sub-steps — §4 measures them: **4.3a** ✅ the shared symbol picker becomes virtualised, **4.3b** ✅ `qml/SymbolPicker/` deleted, **4.3c** ✅ `DateRangeOverlay` deleted (dead), **4.3d** ✅ `qml/TimeRangePicker/` → `support/ui_kit/time_range_picker` on `QCalendarWidget` (`BUG-128`, `CS-004`), **4.3e** ✅ `qml/SelectList/` deleted, its four hosts onto `kit.PickerOverlay` (and the read-only one out of the picker shape altogether), **4.3f** ✅ `qml/CheckboxList/` + `qml/Capital/` deleted — `kit.ChecklistOverlay` arrives for the two checklists, and the capital form keeps `BUG-064`'s lesson with one writer instead of three bindings, **4.3g** ✅ `qml/StatCardRow/` deleted — the performance figures stop being cards (HLD §11.3), **4.3h** ✅ `qml/TradeLogTable/` deleted — measured dead, its two pure files moved to `screens/backtest/logic/`, **4.3i** ✅ `qml/StatGrid/` + `qml/DataTable/` deleted — dead too, the second losing its last caller *to 4.3h*, **4.3j** ✅ `qml/MetricsDetailPanel/` → a `QDialog` on a `QTreeWidget`, leaving `qml/` holding only `kit/`, **4.3k** ✅ `charting/TimeframePicker/` → a pill row of `QPushButton`s and a `QTreeWidget` picker sharing one selection, then `MetricsDetailPanel`/`StatCardRow`/`TradeLogTable`, `DataTable`/`StatGrid`, `charting/TimeframePicker`, and `qml/kit/` last. `find src -name '*.qml'` **24 → 8**, all of them `qml/kit/`'s, and → 0 when they are all gone | the one step with real UI work in it, and the only one the user sees |
| **4.3m** | `strategy` contributes `SignalFeed`, `StrategyArmingCoordinator`, `StrategyCardViewModel`, `strategy_overlay.*` and `strategy_params.strategy_params_dialog` onto `trading`/`dashboard`/`backtest`'s surfaces via `contribute()` + `Place`, instead of those screens importing them directly | found starting 4.4, not a file move — see the ADR and §3.14. **Blocks 4.4** |
| **4.4** | `screens/backtest` → `modules/backtesting/ui/`; `screens/dashboard` and `screens/trading` → `modules/trading/ui/` (4.1c's fold); `screens/data_management` → `modules/market_data/ui/` (4.2b's fold); `sync_progress_{feed,report}` + `symbol_options_coordinator` → `modules/market_data/ui/`, `base_event_logger` → `modules/backtesting/ui/` (4.2a's fold); `ui/common` deleted; `binance_bot_module.py` deleted; settings becomes a surface | every remaining blocker is 4.3's; folding 4.1c, 4.2a and 4.2b in is what keeps every leaf file's move in the same commit as all of its consumers, §3.12 — and now 4.3m, §3.14 |

After 4.1a and 4.2a, `ui/common` holds **two** files: `live_order_book_coordinator` (waiting on
`order_book`, so 4.1b) and `qml_property` (which dies with the QML, so 4.3). Step 4's *"delete
`ui/common/`"* is therefore 4.3's consequence rather than a task of its own.

### 3.3 `sync_progress_*`: the open question is closed by a rule, not by a preference

Step 3 left the destination open for the user because HLD §3.5 assigns the pair to
`support/ui_kit` while §6.1 forbids `support/* → modules/*` with no contracts exception, and
`sync_progress_feed` reads `modules.market_data.contracts.events.sync_events`. Re-read as a
question of *what is legal*, there is only one answer: `support/ui_kit` is refused by the rule
table (`boundaries/rules.py::import_is_allowed` returns `False`), so the only destination that
does not require changing a rule the user already has is `modules/market_data/ui/` — which is
also what the code says it is, a feed whose whole job is to normalise one module's events.

Recorded here as a decision taken rather than a question deferred (`ONBOARDING` §7: a choice with
one legal answer is not the user's to make), and it changes what the epic promised, so it is written
down in the place that promised it: HLD §3.5's row is corrected with 4.4 (§3.12 folds the pull
request that was going to carry this move, 4.2a, into 4.4).

### 3.4 What `ui/components/strategy_overlay/` and `strategy_params/` were

Two directories holding nothing but `__pycache__`. PR 2.1e moved their contents into
`modules/strategy/ui/` and `git` does not track empty directories, so they survived the move
invisibly — the same way `src/application/` and three of `src/domain/`'s subtrees survived PR 3.1c
until they were looked for. Deleted with 4.1a. This also answers step 2's *"`components/
strategy_params` did not come, and it is open for the user"*: **PR 2.1e answered it** — the form
renders *a strategy's* parameters, so it went to `modules/strategy/ui`, and `EPIC-025C` carries the
measurement (`bot_params_form.py` needs `BaseStrategy`, and §6.1 forbids a support package
importing a module at all, so `support/indicators` was never satisfiable).

### 3.5 PR 4.1a's first attempt moved `order_book`, and the ratchet refused it

Worth recording because the refusal was **correct** and the reason is not the obvious one.

`components/order_book` measures 0 legacy imports and reads only
`modules/trading/contracts` (×9) and `support/ui_kit` (×3) — a clean leaf, `assets/`'s position in
PR 1.6a. It was moved. `test_presenter_duplication_only_shrinks.py` then failed: the total across
every pair went **115 → 123**.

The first hypothesis was measurement noise, since a new `trading.ui` package makes the tool compare
`order_book` against packages it never could before. Measured, that is wrong: excluding `__init__`
brings it to 122, and excluding **every** Qt-mandated override name on top of that still leaves
**118**. The five names that remain are `_display_text`, `_sort_value`, `row_for`, `selected_row`
and `refresh`, shared with `screens/data_management` — and they are a **sortable table model plus
panel** written twice: PR 0.4b wrote the pair for Database Status, PR 1.4b-2 wrote it again for
positions and open orders, and neither could see the other because `presentation/ui/components/` was
never in `UI_PACKAGE_GLOBS`. That is the same hole PR 2.1e found for `common/` and `components/`,
and `ci-rule.md` §5.5 forbids raising a ratchet to get past it.

**Put to the user with both scopes measured, and they chose to reorder** rather than widen 4.1a: the
extraction happens **once**, when `order_book` and `data_management`'s models move into their
modules together (4.1b), instead of touching these four model classes in one pull request and again
two later. The cost is named: `screens/trading` waits one extra pull request, so the *"59 duplicated
members → 0"* criterion starts falling at 4.1c rather than 4.1a.

What 4.1a became is the six feeds — which is where the ratchet earned its keep a second time, in the
other direction.

### 3.6 `_subscribe`, and the one amendment the metric's definition has ever taken

With the six feeds moved, the total was **116** against a baseline of 115, and the single name
responsible was `_subscribe`: `BaseFeed`'s `@abstractmethod`, which PR 1.6c put into
`support/ui_kit` precisely so that every feed could share it. `modules/strategy/ui`'s feed
implements it, `modules/trading/ui`'s six now do too, and the tool counted the shared base class as
duplication.

That is a defect in the measurement rather than duplication in the code — implementing one
abstraction in two packages is the *opposite* of duplicating it — so the tool's definition took its
first amendment. `measure_duplicate_members.py`'s docstring says the definition is fixed and must
not be *"improved silently"*, so the amendment is argued in that docstring, computed rather than
hand-listed (`@abstractmethod` declarations under `src/support/` and `src/core/` only), and
deliberately too narrow to reach §3.5's real duplication: Qt's `rowCount`/`data`/`headerData` are
**still counted**, because nothing in this repository declares them, and so are `_display_text` and
`_sort_value`.

**The baseline was then re-measured on the pre-move tree under the amended definition** — 113, not
lowered to fit — so the ratchet still compares like with like. Post-move it is also **113**, with the
Phase 1 pair at **34**.

### 3.7 The finding the move surfaced: `trading` had an undeclared dependency

`TradingModule.dependencies` was `[]`, with a comment explaining that this context *"reads no other
module's `contracts/` — it is the supplier in every relationship it has"*. True of every file under
`modules/trading/` at the time, and false the moment `market_tick_feed` arrived: it normalises
`market_data`'s published `MarketTickEvent` onto a Qt signal for the live chart, which is the Open
Host Service relationship HLD §02 has drawn since round 1. The coupling did not arrive with the
move — only its visibility did, and `test_module_declarations.py` failed on the shortfall within a
minute of the files landing. Fourth time in this epic that the declaration guard has found a real
edge nobody had written down.

### 3.8 PR 4.1a's gate

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → `RESULT: PASS`, **4952 passed, 4 skipped** in
190s, log `logs/ci-local-20260916-152411.log` grepped rather than the console: 4 hits for
`FAILED|ERROR|Traceback|ResourceWarning` (the known benign set) and **0** records matching
`- (WARNING|ERROR|CRITICAL) -`.

Test count **unchanged at 4952**, and that is the expected answer rather than a suspicious one:
`test_logging_namespace_guard.py` parametrizes per source *file name*, and a moved file keeps its
name. No test was written, moved in spirit or deleted — four test files moved with their subjects
and kept their ids.

mypy clean on **486** source files, up from 480. Those six extra files are the point: mypy excludes
`src/presentation/` **wholesale**, so a feed leaving that tree is type-checked for the first time.
PR 2.1e found two real type errors this way; these six were already sound.

The two ratchets, both verified as failing before they were satisfied: the boundary guard listed all
twelve violations before the allowlist entries were written, and
`test_module_declarations.py` failed on `trading: imports contracts from ['market_data'] without
declaring it` within a minute of the files landing — which is §3.7's finding, found by the guard
rather than by reading.

### 3.9 PR 4.1b — the extraction the user asked for, and a metric that had to be fixed twice

`support/ui_kit/table_model.py` is the shared home §3.5 measured the need for. Its own docstring
carries the design argument; what belongs here is the measurement and the two findings.

**What was duplicated, exactly.** Four models — `PositionsTableModel`, `OpenOrdersTableModel`
(PR 1.4b-2) and `DatabaseStatusTableModel`, `KLineInspectorTableModel` (PR 0.4b) — had
`rowCount()`, `columnCount()`, `headerData()` and `row_for()` **byte-for-byte identical**, a `data()`
differing only in which extra roles it served, and `SORT_ROLE` and `_as_number()` each defined
**twice at module level**. The module-level pair is worth naming: `measure_duplicate_members.py`
counts only a `def` inside a `class`, so those two copies were invisible to the metric *and* to the
comment in `table_models.py` that had already written the fix down — *"the shared home for both is
`support/ui_kit` in Phase 4."* This is Phase 4.

`RowTableModel[TRow]` now owns Qt's contract plus `data()` as a template; a subclass declares
`HEADERS`, `RIGHT_ALIGNED`, `_display_text()`, `_sort_value()` and optionally `_role_data()`. The two
`@abstractmethod`s follow `BaseFeed`'s pattern rather than `ABC`, because
`QAbstractTableModel`'s Shiboken metaclass will not mix with `ABCMeta`; PEP 695 generics on a
`QObject` subclass were **tested before the file was written** rather than assumed, which is what
keeps `row_for()` returning `TRow | None` instead of `Any` in a tree mypy actually checks.

`DatabaseStatusTableModel` is why the base holds its rows in a `list`: it re-scans one shard at a
time through `upsert_row()` and emits `dataChanged` for that row alone, so forcing it through
`set_rows()` would reset the model and throw away the user's selection and scroll position on every
scan. `KLineInspectorTableModel` lost its `__init__` entirely (it did nothing but call `super()`) and
keeps `_sort_value()` returning display text with the reason written at the line: that table is
deliberately **not** sortable, and the method is declared abstract rather than defaulted precisely
so a table that *does* need numeric sorting cannot get it wrong in silence.

**The numbers.** Total across every pair **112 → 112**, the Phase 1 pair **34 → 32**. The extraction
alone took the total 113 → 112; moving `order_book` and `live_order_book_coordinator` in then cost
**nothing**, which is the whole point — before the extraction that same move had cost **+8**.
Allowlist **44 → 58**: fourteen entries, none retired, argued inline and retiring together with
4.1a's twelve at 4.1c.

**Finding 1: the metric's amendment was wrong, and the second attempt is the right rule.** PR 4.1a
had excluded names declared `@abstractmethod` under `src/support/` and `src/core/`. That is a
*proxy* for "a shared base class declares it", and it failed on the first hook that was deliberately
not abstract: `_role_data` has a `return None` default so a table with no extra roles need not
implement it, and two of `RowTableModel`'s four subclasses override it — so the total read 114
against a baseline of 113 for a pull request that *removed* duplication.

Two candidate rules were measured before either was written:

| Rule | Excluded names | Total |
| :--- | :-: | :-: |
| every `@abstractmethod` under `support/`, `core/` (4.1a's) | 43 | **114** |
| every method of every class under `support/`, `core/` | 564 | **104** — excuses ten pairs |
| **a name declared by a shared base class this package subclasses** | per package | **112** |

The middle row is why the obvious widening was refused: a support class somewhere defines
`_build_ui`, `_apply` and `_choose`, so excluding every such name would silently excuse ten pairs of
real duplication, and a metric that excuses duplication is worth nothing. What shipped is the third:
per package, read the base classes its own classes name, keep the ones that are classes under
`support/` or `core/`, exclude exactly those classes' methods **for that package only**. Resolved by
name rather than by import, deliberately, so the metric still runs on a tree mid-move.

The test of whether it is narrow enough is what it still counts: `selected_row`, defined
independently by Data Management's panel and by the two order-book panels, remains on the books as
`data_management+trading.ui: 1`. That is the next real duplication — a *panel* shape, where this
pull request removed a *model* shape — and it is 4.2b's or 4.4's, not something to widen a rule
over. The baseline was again re-measured on the pre-change tree under the amended definition (112)
rather than lowered to fit.

**Finding 2: a real type error, in the file that left `presentation/`.** `order_book/preview.py`
built its `LivePosition` fixtures with `liquidation_price=Decimal(...)`, where the field is a
`LiquidationPrice` `NewType` that exists — says its own comment — *"so a locally-computed price can
never be passed where an exchange-reported one belongs"*. Harmless at runtime in a preview fixture,
and invisible for as long as the file sat under `src/presentation/`, which mypy excludes
**wholesale**. Fixed by wrapping, which is also the honest statement that the fixture stands in for
what the exchange said. Third time in this epic that moving a file out of `presentation/` has
produced a real type error on the first mypy run (PR 2.1e found two).

**The E12 probe, and it answers a question the tests alone could not.** Both families' tests passed
after the rebase, but passing does not prove they *go through* the extracted class rather than
merely importing it. Breaking one line — `data()`'s `if role == SORT_ROLE:` branch in
`support/ui_kit/table_model.py` — fails **7** tests across **both** trees at once:
`test_pnl_sorts_by_the_number_not_by_its_text` and
`test_it_cancels_the_row_the_user_sees_after_sorting` under `modules/trading/ui`, and
`test_candle_counts_sort_as_numbers_not_as_text`,
`test_intervals_sort_by_duration_not_alphabetically` and
`test_a_count_that_is_not_a_number_sorts_below_every_real_count` under `data_management`. One line,
two bounded contexts, seven promises — which is the evidence the extraction is real.

No new test. The four models' existing tests are the proof, and they now exercise one
implementation instead of four (`testing-rule.md` §1's "an existing test shown to already cover it"
branch); `RowTableModel` has no behaviour its subclasses' tests do not drive.

**Finding 3: a guard's hard-coded path, and the gate is what found it.** `RESULT: FAIL` on the
first run, three failures in `test_trading_view_contract.py`, all of them a `FileNotFoundError`
inside `ast.parse()`: the guard's `_PRESENTER_SIDE` tuple named
`_SCREEN_DIR.parents[1] / "common" / "live_order_book_coordinator.py"`, and that file had just
become `modules/trading/ui/`'s. This is the reviewer's J4 — *"a guard's own file moved, did its path
constant follow"* — and it is the check my pre-gate run could not make, because I had run
`tests/unit/architecture` and this guard lives under `tests/unit/presentation/`.

Failing loudly was the right behaviour; what was wrong is that it took a three-minute gate run to
say so, and it said it as a stack trace rather than as a sentence. So the fix is three things, not
one: the path now points at the module, `_REPO_ROOT` is found by **landmark** instead of
`parents[6]` (`test_no_root_is_found_by_counting.py` exists because a hop count breaks on every move
this epic makes, and it had already cost PR 1.6f and PR 1.6g a run each), and a new
`test_every_presenter_side_path_exists` names any missing file in milliseconds. The next move that
touches this list gets a sentence instead of a traceback.

### 3.10 PR 4.1b's gate

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → **FAIL on the first run** (finding 3 above,
3 failed / 4950 passed, log `logs/ci-local-20260916-154118.log`), then `RESULT: PASS` on the second:
**4954 passed, 4 skipped** in 188s, log `logs/ci-local-20260916-154555.log` grepped rather than the console —
4 hits for `FAILED|ERROR|Traceback|ResourceWarning` (the known benign set) and **0** records
matching `- (WARNING|ERROR|CRITICAL) -`.

mypy clean on **495** source files, up from 486 — and finding 2 is what those nine extra files
bought.

Test count **4952 → 4954**: two source files added (`support/ui_kit/table_model.py` and the
`test_every_presenter_side_path_exists` guard), one of which the logging namespace guard
parametrizes over and the other of which is itself a test. Four test files moved with their subjects
and kept their ids.

### 3.11 §3.1's finding is **wrong**, and the user's original decision was right

`screens/trading` reached **0** legacy imports after 4.1a and 4.1b, exactly as §3.1 predicted. It
still cannot move on its own, and §3.1's conclusion — *"the pair splits, and the criterion starts
falling at 4.1c rather than after the deletions"* — is retracted here rather than left standing.

**What §3.1 measured, and what it forgot to.** It measured *legacy imports*, which is what decides
whether a move is **legal**. The epic's headline criterion is decided by something else:
`tools/measure_duplicate_members.py`, with a shrink-only ratchet on it. Simulated before moving a
file — `screens/trading`'s members merged into the existing `trading.ui` package, since that is what
the move does:

| | before 4.1c | after 4.1c |
| :--- | :-: | :-: |
| total across every pair | 112 | **112** |
| `dashboard+trading` | 32 | — (the package is gone) |
| `dashboard+trading.ui` | — | **39** |
| `phase_1_count`, keyed `("dashboard", "trading")` | 32 | **0** |

Three things in that table, in order of how badly they matter:

1. **The total does not move.** The 39 names are still defined twice; the move deduplicates
   nothing. That is the honest number and it is why the total-across-every-pair ratchet exists —
   PR 2.1e added it after finding the Phase 1 pair falling while duplication merely relocated.
2. **`phase_1_count` would read 0.** The epic and `PRO-004` are judged on that number reaching zero,
   and it would reach zero by *renaming a package*. The tool's own docstring claims this cannot
   happen — *"Renaming a package moves its count; it cannot hide it"* — and it is right about the
   **total** and wrong about this key, because `PHASE_1_PAIR` is two literal package names.
   `test_the_baseline_was_lowered_when_duplication_went` would then lock the false 0 into the
   baseline, and the criterion would be permanently unfalsifiable.
3. **Re-keying it honestly makes the ratchet rise**, 32 → 39, which `ci-rule.md` §5.5 forbids
   outright. The 39 is not new duplication; it is the same duplication the pair was always carrying,
   re-counted now that `trading`'s two halves are one package. But a ratchet that goes up is a
   ratchet nobody can trust afterwards.

So there is no version of 4.1c that ships alone. The two live screens travel **together**, after
the QML deletions, which is what the user's
[`DECISION_2026-09-16`](../DECISION_2026-09-16_the_duplication_criterion_waits.md) said in the first
place: *"the criterion travels with the deletions in this step."* `screens/dashboard` still has 9
legacy imports, 6 of them QML that ADR D21 deletes, so it is 4.3's dependency and 4.1c folds into
4.4.

**What 4.1a and 4.1b were worth anyway**, since the pull request they were supposed to unblock has
moved: the feeds and `order_book` are in `modules/trading` where HLD §3.5 always put them, the Phase
1 pair fell **39 → 32** on real de-duplication rather than on relocation, the total fell 115 → 112,
four table models became one class, and three findings came out of them (§3.6, §3.9's three). None
of that depended on 4.1c.

**The lesson, and it is the second time in this phase.** §3.5 found that a move a *legality*
measurement called free was refused by a *duplication* measurement. §3.11 finds the same thing one
step further along: legality and the ratchets answer different questions, and Phase 4's cut has to
be measured against **both** before a file moves. §3.2's table is corrected accordingly.

---

## 4. PR 4.3's cut, measured 2026-09-16

27 `.qml` files: **24** under `presentation/ui/qml/` and 3 under
`support/charting/TimeframePicker/`. Nothing is dead — the first reading said `DataTable` and
`StatGrid` had no consumer, and re-checking (PR 3.1a's lesson, twice paid) found both are imported
by **other QML**: `TradeLogTable.qml` uses `DataTable`, and `kit/DialogShell.qml` pulls in
`Capital`, `CheckboxList`, `SelectList` **and** `StatGrid`. So there is no deletion-only pull
request here; each package dies when its *Python* consumer stops loading it.

| QML package | `.qml` | `.py` | Python consumers |
| :--- | :-: | :-: | :--- |
| `kit` | 8 | 13 | `backtest_top_panel`, `data_management_view`, `dev_board_panel` — and every other QML package |
| `SymbolPicker` | 3 | 10 | the Backtest and Dev Board picker dialogs |
| `TradeLogTable` | 2 | 9 | 5 backtest files |
| `MetricsDetailPanel` | 2 | 9 | 4 backtest files |
| `TimeRangePicker` | 2 | 8 | backtest modal, `time_range_card` (Data Management), `dev_board_panel` |
| `DataTable` | 2 | 5 | none in Python — `TradeLogTable.qml` |
| `StatCardRow` | 1 | 7 | `backtest_top_panel` |
| `SelectList` | 1 | 1 | 3 backtest modals + `market_picker/overlay` |
| `CheckboxList` | 1 | 1 | 2 backtest modals |
| `Capital` | 1 | 1 | 1 backtest modal |
| `StatGrid` | 1 | 1 | none in Python — `DialogShell.qml`, `MetricsDetailPanel.qml` |
| `abstract` | 0 | 1 | **one colocated test under `src/`, which the gate never runs** |

That last row is PR 1.4b-2's finding still standing: 20 test files live under
`src/presentation/ui/qml/*/tests/`, the gate runs `pytest Sagittarius_Elite_Warrior/tests`, so
those tests have never run in it and whatever they guard is unprotected. They go with their `.qml`.

**What decides the shape of each replacement is already written down**, which is why no part of this
needed a new decision: HLD §11.2 maps `MODAL` → `QDialog`; §11.3 **retires the card** outright on
the user's own judgement (*"các card cũ cũng rất là tệ"*) and gives the replacement for a list of
things as *"a table (`QTableView` on a model)"*; §11.4's ratchet counts what styling is left and
deletes `Palette` and `kit/style.py` in this phase, *"together with the last `.qml` file and the
last `kit/` widget"*.

### 3.12 4.2a folds into 4.4, and the reason is a rule plus a precedent neither of us had checked

Raised as an open question in PR #223 (the `BUG-129` fix), rather than decided there: PR 4.2a as
planned — `sync_progress_{feed,report}` + `symbol_options_coordinator` → `modules/market_data/ui/`,
`base_event_logger` → `modules/backtesting/ui/`, moved on their own ahead of the screens that use
them — was never re-checked against `BOT-134`'s rewritten `architecture-rule.md` (*"the allowlist
only shrinks"*) or against what those four files' callers actually are.

**Measured, not assumed.** Grepping the real import lines (not just filenames) finds seven legacy
files importing the four movers, ten import lines total: `screens/backtest/signal_wiring.py` (1),
`screens/backtest/backtest_presenter.py` (2), `screens/backtest/logic/backtest_event_logger.py` (1),
`screens/data_management/data_management_presenter.py` (2),
`screens/data_management/coordinators/sync_coordinator.py` (1),
`screens/dashboard/dashboard_presenter.py` (2), `screens/dashboard/stream_lifecycle_controller.py`
(1). Moving the four alone means all ten become new cross-boundary imports needing an allowlist
line apiece: 58 → 68, exactly the number PR #223 cited and exactly what the rewritten rule now
forbids outright, with no shrink to offset it in the same pull request.

**Sequencing does not fix it, because every one of those seven files is itself already scheduled to
move — into 4.2b or 4.4.** The allowlist cost is not a property of the four leaf files; it is a
property of the *gap in time* between a leaf file's move and its last consumer's move. Moving the
leaf files with 4.2b (whose only consumers are two of the seven) still leaves the other five —
`backtest` and `dashboard`'s — as new cross-boundary imports until 4.4 lands; moving them with 4.4
leaves 4.2b's two the same way if 4.2b goes first. The only sequencing with **zero** new lines at
any point is moving each leaf file in the same pull request as every one of its consumers — which
for `sync_progress_{feed,report}` means 4.2b and 4.4 at once, since both `data_management` and
`backtest`/`dashboard` import them.

**A second problem, worse than the ratchet: `symbol_options_coordinator` would set a precedent this
codebase has never had.** It already imports `modules/market_data/contracts/i_symbol_catalog`
directly (line 20), so `support/ui_kit` is not a legal destination either — §6.1 forbids a support
package importing a module at all, contracts included. `modules/market_data/ui/` is its only legal
home. But its callers are `screens/backtest/backtest_presenter.py` and
`screens/dashboard/dashboard_presenter.py`, which are moving into `modules/backtesting/ui/` and
`modules/trading/ui/` — two *different* modules. Grepping every `modules/*/ui/**` import in the
tree today (`strategy` and `trading`, the only two with a UI package so far) finds every one of them
reaching into its **own** module's `domain/`, `application/` or `ui/` — never another module's `ui/`
package. Landing 4.2a as planned would have made `backtesting.ui` and `trading.ui` import
`market_data.ui` directly, the first case of one module's UI depending on a concrete class in
another module's UI rather than through `contracts/` — a hole neither this file nor
`architecture-rule.md` §2 currently guards against, because nothing had done it yet.

**Put to the user with both findings and the fold measured at zero cost: fold 4.2a into 4.2b and
4.4, merged into one pull request** (2026-09-17). The alternative — publishing a new port so
`symbol_options_coordinator` need not be a concrete class two other modules' UIs import — was
offered and declined in favour of the smaller-design-surface option: the three screens and the four
leaf files move together, so the cross-module UI import never has to exist even transiently. `4.4`'s
row in §3.2 carries the merged scope; 4.2a and 4.2b are struck there rather than deleted, so the
measurement above stays attached to the decision it produced.

### 3.13 Correction to §3.12's second finding — the precedent already exists

Measuring PR 4.4's actual scope (step 4 of the `epic-025` executor's checklist, before touching any
code) found §3.12's "no `modules/*/ui` file imports another module's `ui/`" claim false. The grep
it was based on only searched files already living under `modules/*/ui`; `screens/trading`,
`screens/dashboard` and `screens/backtest` are still legacy, so their imports of
`modules.strategy.ui.signal_feed`, `.strategy_arming_coordinator`, `.strategy_card_view_model`,
`.strategy_overlay.*` and `.strategy_params.*` — eleven files' worth, dating to PR 2.1e, reviewed
and merged — never showed up. The moment any one of these three screens moves into its own
module's `ui/`, this pattern becomes exactly the cross-module UI import §3.12 called
unprecedented: `modules/trading/ui` (or `backtesting.ui`) importing `modules/strategy/ui` directly,
already true today in legacy form.

**What this changes and what it does not.** `symbol_options_coordinator` landing in
`modules/market_data/ui/` and being read by `backtest_presenter.py`/`dashboard_presenter.py` would
not have been a first case — `strategy.ui` already publishes concrete display widgets other
screens depend on directly, on the theory (never written down until now, so writing it down here)
that "the armed strategy's card" and "the symbol catalog's picker" are each one module's own
concept, and a screen rendering it is not the same shape as two modules' *business logic* reaching
into each other. The fold decision from §3.12 is unaffected: the boundary-allowlist arithmetic
(58 → 68, forbidden outright) is the argument that actually carries it, independent of the
precedent question.

**This paragraph was itself wrong about what the precedent means, corrected the same day by
actually running the guard rather than grepping it.** "The precedent already exists, so it is not
unprecedented" reads as "so it is fine" — it is not. `boundaries/rules.py::_module_may_import`
allows a module to import another module **only** through `contracts/`, with no `ui/` exception,
and it does not care that the shape already existed in legacy form: the moment `screens/trading`
(or `dashboard`, or `backtest`) actually becomes a module, `test_module_boundaries.py` fails on
exactly these imports — reproduced by moving `screens/trading`'s nine files and running the guard,
before writing anything else. `symbol_options_coordinator` landing in `modules/market_data/ui/`
would still be refused the same way if any *other* module's screen imported it directly, which is
moot here since nothing does yet. What §3.12's fold decision got right stands; what this paragraph
got wrong is superseded by `DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`
and PR 4.3m below.

### 3.14 PR 4.3m — `strategy` contributes its UI; three screens stop importing it directly

New step, found while starting PR 4.4 and not decided here: see the ADR
(`DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`) for the finding, the
alternatives, and why the user chose the full redesign over widening the boundary rule. Blocks PR
4.4 — `screens/trading`, `screens/dashboard` and `screens/backtest` may not become modules while
they import `modules.strategy.ui.signal_feed`, `.strategy_arming_coordinator`,
`.strategy_card_view_model`, `.strategy_overlay.*`, `.strategy_params.strategy_params_dialog` or
`modules.strategy.application.services.strategy_registry` directly. Its own scope, sequencing and
measurements are not written yet — the three open questions in the ADR (§4, O1–O3) are where that
starts.

### 4.1 PR 4.3a — the symbol picker had **two** implementations, one per toolkit

The measurement that reordered this step. `support/ui_kit/symbol_picker/` holds a QtWidgets
`SymbolPickerOverlay`, used by Data Management. `presentation/ui/qml/SymbolPicker/` holds a QML one,
used by Backtest and Dev Board. They are the same dialog, and the QML one's docstring says exactly
why it exists: *"Replaces `SymbolPickerOverlay` for Dev Board (Dashboard), eliminating UI freeze
when displaying thousands of symbols via virtualized QML GridView."*

So ADR D21 cannot simply delete the QML picker: the QtWidgets one built **one `SymbolCard` widget
per entry** into a `QGridLayout` (`overlay.py:335`), which with the exchange's ~1400 pairs is 1400
widgets constructed on every keystroke. That is the freeze, and it was real.

4.3a fixes the freeze in the toolkit the app is keeping, so that 4.3b can delete the QML one without
reintroducing it. `SymbolPickerOverlay`'s results area is now a `QTableView` on a new
`SymbolTableModel(RowTableModel[SymbolEntry])` — three columns (the pair, why it matters, the star)
— which virtualises natively: the view asks `data()` only for the rows it is about to paint. It is
also HLD §11.3's own answer rather than an invention, and it retires `SymbolCard`, which was a
`SelectableCard` and therefore exactly what §11.3 retires. **`RowTableModel` is PR 4.1b's**, one
pull request old, which is the second consumer that justified extracting it.

**The star is a column, not a painted hit-rect.** `QTableView` reports the index it was clicked on,
so "did the user star this row or choose it" is a column comparison — the platform doing the work
a custom delegate would otherwise do with mouse arithmetic.

**One promise was deliberately dropped**, and it is the only user-visible loss: the two section
headings, "FAVOURITES" and "ALL RESULTS". A heading between two groups of rows cannot live inside
one virtualised view, and on the Favourites tab it labelled every row anyway. The *pinning* those
headings described is kept and still asserted; what marks a favourite now is the filled star on its
own row, which is also what the user clicks. Two promises were **added** rather than lost: the
current symbol's row is under the keyboard on open (so Enter works without an arrow key first), and
the highlight still wraps at the end.

The twelve existing tests were restated promise by promise rather than made to pass —
`test_symbol_picker_overlay.py`'s docstring carries the inventory table (`pr-review` E11), and the
five Data Management picker tests that reached through `_cards` were retargeted the same way with a
note that nothing about that screen's behaviour changed.

**And the promise this change exists for was pinned by nothing**, in either implementation:
`test_a_long_symbol_list_creates_no_widget_per_symbol` builds a 20-symbol dialog and a 1400-symbol
dialog and asserts the widget count is the **same** — a comparison rather than an absolute, since
the absolute is Qt's business (`ONBOARDING` §8 trap 3). Probed: adding one `QLabel` per row inside
`_rebuild()` fails exactly that test and nothing else, which is also the evidence that the old card
implementation would have failed it.

§11.4's ratchet moved and was lowered in the same commit, as that section requires:
`apply_role` calls **52 → 49** across **26 → 25** files. The QML numbers are untouched — 4.3a
deletes no `.qml`; 4.3b does.

**Gate:** `RESULT: PASS`, **4958 passed, 4 skipped** in 188s, log
`logs/ci-local-20260916-161525.log` grepped rather than the console — 4 hits for
`FAILED|ERROR|Traceback|ResourceWarning` (the known benign set) and **0** records matching
`- (WARNING|ERROR|CRITICAL) -`. mypy clean on 495 source files. Test count **4954 → 4958**: four
net, from three promises added (the virtualisation test, the star-marks-a-favourite test, the
current-row-under-the-keyboard test, the wrap test) against one source file added and one deleted,
which cancel in the logging guard's per-file parametrization.

### 4.2 PR 4.3b — the QML picker is deleted, and one signal had to come with it

`presentation/ui/qml/SymbolPicker/` is gone: **3 `.qml` + 10 `.py`**, four of those Python files
being colocated tests the gate never ran. `qml/abstract/` and `qml/interfaces/` went with it — each
held exactly one file, and both existed only for that picker.

`ISymbolPickerSource` is **not** deleted, and it moved to
`support/ui_kit/symbol_picker/i_symbol_picker_source.py`. It is still the right seam: two screens
implement it, each translating its own ViewModel into the four questions a picker asks, and
`architecture-rule.md` §5 is why those adapters do not live in the dialog files that construct them.
`SymbolPickerOverlay` takes four callables, so a caller with nothing to adapt — Data Management
reads its ViewModel directly — never sees the file.

**The finding: one promise was carried by the QML host and nothing else.** Opening the picker asked
the screen to refetch its symbol list from the exchange — Backtest connects
`refreshSymbolOptionsRequested` in `signal_wiring.py`, Dev Board connects
`symbolOptionsRefreshRequested` in `dashboard_presenter.py`. `SymbolPickerOverlay` had no such
signal, because Data Management never needed one (its own scan populates the list). Deleting the
QML host without noticing would have left a user who opened the picker before the exchange answered
sitting on "Loading…" until they closed and reopened it. So the overlay gained
`refresh_requested`, emitted in `showEvent()` **before** the lists are re-read — synchronous hosts
are then read by the same open, asynchronous ones call `refresh()` when their answer lands.

**Seven tests went with their subject, and four of their promises did not.** The E11 inventory is in
the new `tests/unit/presentation/ui/screens/backtest/test_symbol_picker_dialog.py`: refetch-on-open,
choose-writes-through-and-records-recent, star-without-choosing and swap-the-preferences-store all
have homes there, plus a new one for un-starring (the overlay reports only *which* symbol was hit,
so the dialog is what turns that into an add or a remove, and a dialog that only ever added would
make un-starring impossible). Three were dropped with the toolkit that created them: two were about
an inner QML `Popup` leaving the outer `QDialog` on screen (`qml-rule.md` §0.1 — there is one widget
now, so no shell to strand) and one was about a broken `.qml` file.

`test_dev_board_panel.py`'s `BUG-066` freeze test named *"SymbolPicker.qml virtualizes items"* in
its docstring. Corrected, and **strengthened**: the wall-clock assertion is the user's own promise
from that bug and stays, and beside it now sits the deterministic one — 1,358 symbols, fewer than a
hundred widgets.

**The numbers.** `.qml` **27 → 24**, and both ratchets were lowered in the same commit as their own
rules require: `baseline_qml_files.txt` lost its three lines, `baseline_app_styling.json`'s
`qml_files` **27 → 24** with `apply_role` **49 → 48** across **25 → 24** files, and the duplication
total **112 → 107** (the two picker dialogs stopped being QML hosts with a shared set of method
names). The Phase 1 pair is unchanged at 32.

**Gate:** `RESULT: PASS`, **4944 passed, 4 skipped** in 190s, log
`logs/ci-local-20260916-173900.log` grepped — 4 hits for
`FAILED|ERROR|Traceback|ResourceWarning` (the known benign set) and **0** records matching
`- (WARNING|ERROR|CRITICAL) -`; mypy clean on 496 source files. Test count **4958 → 4944**, and
every one is accounted for: **−8** the two deleted test files' tests, **−11** the logging namespace
guard's per-source-file rows for the eleven deleted `src/` files, **+5** the new dialog test file.
The moved port keeps its file name, so its row is unchanged.

**E12:** breaking `self.refresh_requested.connect(self._vm.refreshSymbolOptionsRequested)` fails
exactly one test — the refetch one — and nothing else.

### 4.3 PR 4.3c — the *other* duplicated picker, and this one was dead

`TimeRangePicker` turned out to be the symbol picker's story again, with a sharper ending.
`time_range_picker_vm.py`'s own docstring names it: *"Generalises
`kit/overlays/date_range_overlay.py`'s `DateRangeOverlay` (presets + two-month calendar) to the QML
widget shape."* So the app carried **two** date-range pickers as well — and **both hand-drew the
calendar**, which is precisely what ADR D20 rules out, because `QCalendarWidget` is the component
the platform already has.

The difference from the symbol picker is that this one had no consumer to protect. Measured:
nothing under `src/` has constructed `DateRangeOverlay` since `EPIC-015` gave the job to the QML
picker. The only thing that built it was **`tools/kit_showcase`**, the developer gallery — which is
`CS-002`'s shape one level out: a widget alive because something shows it, not because anything uses
it. Its 454 lines built one `_DayCell(QPushButton)` per day and gave each an inline stylesheet.

So 4.3c is a deletion, PR 3.1a's shape: `date_range_overlay.py`, its 13 tests, its two `kit/`
re-export blocks, and its showcase page. `RangePreset` and `DEFAULT_PRESETS` went with it — measured
first, and nothing outside that file and the showcase named either. The Backtest screen's own
`TimeRangePreset` in `screens/backtest/logic/` is a **different** type and is untouched.

**The ratchet is where this pays.** §11.4 counts four numbers and all four moved, so all four were
lowered in the same commit as that section requires: `apply_role` **48 → 44** across **24 → 23**
files, and — the one that matters — **`setStyleSheet` 149 → 145** across **22 → 21** files, the
first fall in that number this phase. Deleting a widget that painted its own day cells is how the
"no stylesheet anywhere" target actually gets reached.

The QML `TimeRangePicker` is still there and is **4.3d**'s: it is the surviving implementation, and
replacing it means a `QDialog` with a real `QCalendarWidget` rather than a `leftDays`/`rightDays`
grid computed in Python.

**Gate:** `RESULT: PASS`, **4928 passed, 4 skipped** in 189s, log
`logs/ci-local-20260916-174723.log` grepped — 4 hits for the known benign set, **0** records at
WARNING or above; mypy clean on 495 source files. Test count **4944 → 4928**: **−13** the deleted
overlay's tests, **−1** the logging namespace guard's row for the deleted source file, **−2** the
showcase-coverage guard's parametrisations for the two exports that went.

### 4.4 PR 4.3d — the surviving picker, one `QCalendarWidget`, and a bug the gate could not see

4.3c deleted the dead half of the pair. This is the live half: `src/presentation/ui/qml/TimeRangePicker/`,
the one three screens actually opened. It is now `src/support/ui_kit/time_range_picker/`, a `QDialog`
with two real `QCalendarWidget`s, and the QML package is gone — `.qml` **24 → 22**.

**The split is the point, not the widget.** The package is two files because the rules and the
painting have different reasons to change: `range_rules.py` (181 lines) holds `parse_instant`,
`format_instant`, `resolve_preset`, `seed_range`, `can_apply` and `build_summary` — pure functions
over `datetime`, no Qt import — and `dialog.py` (360) holds the calendars, the fields, the preset
row and the summary label. The QML version had these in one `QObject` ViewModel behind `Property`
declarations, which is why its 13 tests needed a Qt event loop to assert that a week is seven days.
The 14 tests in `test_range_rules.py` need nothing.

**The three consumers did not notice.** `screens/backtest/backtest_modals/time_range_picker_dialog.py`,
`screens/data_management/data_management_widgets/time_range_card.py` and
`screens/dashboard/dev_board_panel.py` all constructed the QML dialog through the same signature
(`from_text`, `to_text`, `parent`, then `applied`), so the change is an import swap in three files
and nothing else. That signature was not a coincidence to be grateful for: it is what `EPIC-014`
established, and it is the reason this deletion cost three lines instead of three screens.

**`BUG-128` came out of writing the tests, not out of using the app.** `seed_range`'s ancestor
tested `start is None or end is None or start > end` and then repaired only the first two disjuncts
— an inverted pair is non-`None` on both sides, so both `or` fallbacks kept what they had and the
dialog opened on `08 Jul → 01 Jul` with **Apply enabled**. A guard that detects a state and declines
to repair it; `can_apply` could not catch it downstream, because *present* is a different question
from *ordered*. Fixed as three explicit branches, since the defect **was** a fallback that missed
the case its own condition named. The regression test was written first and confirmed red, returning
the inverted pair.

**And the review of this pull request found the other half of it.** Two calendars remove the old
one-grid picker's disambiguation rule, and they introduce a state that picker could not reach: click
From after To and the pair inverts by hand. `can_apply` said yes to that for exactly the reason it
said yes to the seeded pair — *present* is not *ordered* — so fixing only `seed_range` would have
left the symptom one click away, which is `bug-fix-rule` §2's "the mechanism, not the reported call
site". `can_apply` now requires both ends and their order, and `build_summary` words that state
(*"The end is before the start"*) rather than clamping the negative span to `0 days`, which read as
a legitimate single instant. This file's own test docstring had asserted in prose that two calendars
*cannot* reach an invalid state — true of the state the previous picker reached, false of the one
this shape introduces, and the reason the review row about breaking the line (`E12`) earns its keep:
the new test fails, and only it fails, when `_calendar()`'s `clicked` connection is deleted.

**`CS-004` is the case study, and its check is the one that generalises.** The VM had 13 unit tests,
one of them on that very condition's unparseable branch, and **no run has ever collected them**:
they lived at `src/presentation/ui/qml/TimeRangePicker/tests/`, and the gate runs `pytest tests`.
PR 1.4b-2 found the hole and counted twenty such files; this is the first time it cost something.
`tests/unit/architecture/test_no_test_file_lives_under_src.py` now fails on a new `test_*.py`,
`*_test.py` or `conftest.py` under `src/`, against a shrink-only baseline of the **22** that remain
— all of them inside QML packages 4.3's remaining steps delete, so the list reaches zero with the
last `.qml`.

**One ratchet note worth recording.** The new dialog first **raised** `apply_role` 44 → 46: the
obvious way to write a heading in this codebase is `apply_role(label, "heading")`, and §11.4's
number counts every such call. A widget arriving in the phase whose job is to drive that number to
zero cannot add two. Both were removed and `_heading()` returns a plain `QLabel`, with a docstring
saying why — so the styling baseline moves only on its QML keys: `qml_files` **24 → 22**,
`qml_theme_refs` **188 → 166**. The two `apply_role` numbers and both `setStyleSheet` numbers are
untouched, which is the correct outcome for a PR that deletes `.qml` and adds a widget.

**Six host-side tests had to be restated, and the first gate run is how I learned that.** They
reached into the QML dialog's internals — `_widget_vm.fromText`, `_widget_vm.choosePreset("7d")`,
`find_all_named(dialog.root_object, …)` — so each failed with an `AttributeError` three minutes in,
exactly the shape PR 4.1b hit: they live under `tests/unit/presentation/`, which the pre-gate
`tests/unit/architecture` run does not reach. Every promise was restated rather than deleted
(`pr-review` E11): what an open seeds from, what an Apply writes to both fields and the ViewModel,
that the Backtest modal lists one preset more than its ViewModel's option list (now asserted as the
real number, 7, as well as as a relation), and that Dev Board's picker falls back to a 1m summary
(now checked on the summary text too, not only on the two callables). The move's own test file is
restated one for one: of seven, five keep their names, the `can_apply`-tracking one becomes two, and
the broken-`.qml` one is dropped for want of a subject.

**Gate:** `RESULT: PASS`, **4946 passed, 4 skipped** in 184s, log
`logs/ci-local-20260916-181345.log` grepped — 4 hits for the known benign set, **0** records at
WARNING or above; mypy clean on 498 source files. Test count **4928 → 4946**: **+16** the rules
suite the gate can actually see, and **+2** net in the guards — the new `test_no_test_file_lives_under_src.py`'s
three, less one parametrised row the deleted source files cost. The dialog's own file is 7 → 7.

### 4.5 PR 4.3e — `SelectList` had a replacement already written, and one of its four hosts was never a picker

`qml/SelectList/` was the "choose one from a list" body, shared by four dialogs. Unlike 4.3a's
symbol picker and 4.3c's date-range overlay, **nothing had to be built**: `kit.PickerOverlay`
(PR 1.6b, 240 lines, 16 tests) is the same component in QtWidgets and has served the symbol pickers
and Data Management since. So this step is a survey followed by four rewirings — `onb` §12.5
principle 5's outcome in the cheap direction, for once.

Three of the four are ordinary: `timezone_picker_dialog`, `strategy_picker_dialog` and
`components/market_picker/overlay` each become a `PickerOverlay` subclass with a `refresh()` that
maps the screen's own option shape into `PickerItem`s and a `_on_selected` that writes and closes.
The timezone one gains `searchable=True` on the way, which the component already had and the `.qml`
never did.

**The fourth was the finding: `limitations_dialog` is not a picker and never was.** `EPIC-015` §4c
had served it from `SelectListVM(selectable=False)` on the argument that a read-only bullet list is
a picker with nothing to click — true of a `.qml` delegate that can branch on a flag, and the wrong
shape here, because `PickerOverlay`'s whole contract is *a row can be chosen and emits its value*.
Serving this screen from it would have meant a parameter that switches off the component's only
promise. It is now what HLD §11.3 calls a read-only summary: an `Overlay` over a scroll area of
wrapped labels, one bullet each, built in the dialog rather than promoted to `kit/` because there
is exactly **one** consumer (`base_feed`'s rule — a shape becomes shared when the second one
appears). The empty case says *"This run reported no limitations."* rather than showing a blank box.

**Two defects came out of writing its tests.** The rebuild first took each label out of the layout
and called `deleteLater()`, which is how `PickerOverlay` does it — and a deferred delete is
delivered by the main event loop, not by the call that scheduled it, so between the two the host
still holds the previous run's labels and the "replaces the previous run" test read both runs at
once. `setParent(None)` before the delete is the fix. And the first draft of the strategy test
**skipped** when `strategyOptions` was empty, which a bare `BackTestViewModel` always is: a skip
that covers nothing looks exactly like a pass. It seeds two strategies now, which is what the
Presenter does from the registry.

**Restated, not deleted** (`pr-review` E11). `SelectListVM`'s 13 tests and `SelectList.qml`'s 4 go
with their subject; the component-level promises are `test_picker_overlay.py`'s, which gains the one
the deleted suite covered and it did not — *a selected value no longer on offer marks nothing*, the
state a screen reaches when a strategy is unregistered. The per-dialog promises are restated in
`tests/unit/presentation/ui/screens/backtest/test_select_dialogs.py` (11) and the market picker's
own file (4, same sentences, different way of reaching a row). Two are deliberately dropped:
`selectable=False`'s two behaviours, because the read-only dialog no longer inherits a picker to
switch off, and the broken-`.qml` render pair, for want of a subject. `scanned_roots_registry.py`
loses the row for the deleted guard — a registry row outliving its guard is the silently-empty scan
that file exists to catch, pointed the other way.

`.qml` **22 → 21**, `qml_theme_refs` **166 → 157**; the `apply_role` and `setStyleSheet` numbers are
untouched again, for the same reason 4.4 records.

**Two host tests failed on the first gate run, and that is the third time this phase.** 4.1b's
`FileNotFoundError` and 4.3d's six `AttributeError`s were the same shape: a guard or a host test
under `tests/unit/presentation/` that the pre-gate `tests/unit/architecture` run cannot see. This
time the pre-gate run was widened to `tests/unit/presentation/ui/screens/backtest`, `…/ui/qml` and
`…/ui/components` — and the two failures were in `tests/unit/presentation/ui/screens/`, one
directory **above** all three. The rule this leaves: before a gate, run
`pytest tests/unit/presentation` whole (231s), not the directories the change looks like it touched.
Both were restated — the limitations popup counts `lblLimitation_` labels and now asserts their
**text**, not just the row count; the strategy modal counts `SelectableCard`s.

**Gate:** `RESULT: PASS`, **4936 passed, 4 skipped** in 192s, log
`logs/ci-local-20260916-183909.log` grepped — 4 hits for the known benign set, **0** records at
WARNING or above; mypy clean on 498 source files. Test count **4946 → 4936**, measured file by file
rather than reasoned about: **−12** `test_select_list_vm.py`, **−4** `test_select_list_bodies.py`,
**−3** the timezone trio leaving `test_qml_modal_bodies.py` (6 → 3), **+11**
`test_select_dialogs.py`, **+1** `test_picker_overlay.py` (16 → 17), **−3** in the guards (two
parametrised rows for the deleted source files, one for the deleted `.qml`).

### 4.6 PR 4.3f — the shape `PickerOverlay` refused to guess at, and `BUG-064`'s lesson restated without bindings

Two `.qml` bodies go together here because they are what is left of `EPIC-015`'s "bậc 1 pilots":
`CheckboxList` (two hosts) and `Capital` (one). `.qml` **21 → 19**.

**`ChecklistOverlay` is the first genuinely new `kit/` widget this phase has added, and its
justification was written eighteen months of commits ago.** `PickerOverlay`'s docstring names this
exact shape and declines it: *"The app's indicator picker is multi-select, toggles checkboxes, and
never closes — a genuinely different interaction, not a parameter of this one. Left as a candidate
rather than guessed at, the lesson EPIC-006's four abandoned card stubs paid for."* This is the step
that needed it, and the judgement held: a picker emits *the* choice and its consumers `accept()` on
it; a checklist emits *a* change and its consumers stay open. Two consumers exist, which is
`base_feed`'s bar for a shared widget — unlike 4.3e's read-only list, which had one and stayed in
its dialog.

**The re-entrancy is the design constraint, and it is why `set_items()` is not a plain rebuild.**
`OrderExecutionDialog` has a cross-row rule — two of its four rows are mutually exclusive — and it
enforces that rule the only honest way: the toggle handler writes the screen's state, whose change
signal calls `set_items()` again, *from inside the checkbox's own `toggled` emission*. A rebuild
there would tear down the widget whose signal is still being delivered. So an unchanged key set
updates the existing controls in place (with signals blocked, so writing the state a consumer just
asked for does not return as a second user toggle), and only a changed key set rebuilds. Written as
its own test, because that path exists for this and nothing else.

**Writing that widget's tests found a third defect in my own draft, two PRs running.** The empty
state never appeared: `set_items([])` on a freshly built overlay is an *unchanged* key set (empty to
empty), so it took the in-place path, which touched no visibility. The empty/rows decision now sits
outside both paths. The pattern across 4.3e and 4.3f is worth naming — both defects were in the
branch that skips work, and both were found by a test asserting what is on screen rather than what
the code did.

**`BUG-064` is the interesting half of `Capital`.** That bug was a `QLineEdit`, a `QComboBox`, a
validation `QLabel` and a `_sync_validation()` holding the label and the Apply button in agreement —
three writers of one truth, one of them forgotten. `EPIC-015` answered it by moving to QML, where
the message's text, its visibility and the button's `enabled` are three declarative bindings, and
said so: the bug *"cannot recur in this shape"*. ADR D21 takes that shape away, so the answer had to
be restated rather than re-earned: **one** method, `_render_verdict()`, writes all three from the
presenter's verdict, and nothing else in the file touches them. The failure `BUG-064` describes
needs a second writer to exist, and there is not one. `CapitalVM` is deleted; its one non-rendering
rule — Apply does nothing while the verdict is bad, rather than trusting the button to be disabled —
is kept in `_apply()`, for the reason that VM itself gave.

Two small truths came back with it. `textEdited` rather than `textChanged`, so seeding the field on
open does not read as typing and ask the presenter to validate a value nobody touched. And the
indicator picker gets an empty state again — *"No indicator scripts are registered."* — which the
`.qml` had dropped on the argument that an empty list "reads the same way"; a blank box reads as
*loading*, which is the distinction an empty state exists to make.

**Restated, not deleted.** `CheckboxListVM`'s 5 tests and `CheckboxList.qml`'s 5 render tests become
`test_checklist_overlay.py`'s 14, except `BUG-071`'s (`width: parent.width` on a `QQuickWidget` root
with no QML parent) which has no subject in a layout. `CapitalVM`'s 8 become
`test_capital_dialog.py`'s 8, minus three about that `QObject`'s own mechanics — `canApply` derived
rather than stored, the same-text no-op, `currencies` as a plain list — and plus the one that
matters, that a verdict's three consequences cannot disagree. The order-execution modal's three host
tests lose the two paragraphs they carried about reaching items inside a `Repeater`'s scene graph;
they use `ChecklistOverlay.checkbox_for(key)`, which is public for exactly that reason. The capital
regression test that guards `_build_buttons()`-ordering now drives the **real** presenter instead of
assigning a ViewModel property. `test_qml_modal_bodies.py` has lost both its subjects and is renamed
`test_qml_overlay_load_failure.py` for the third test, which was never about either: a `.qml` that
fails to load must raise rather than render a blank rectangle, and that promise lives until the last
`.qml` does.

**The first gate run failed on `ruff format`, and the cause is worth a line.** 4.3e's lesson was to
run `pytest tests/unit/presentation` whole; this one is the same mistake in the cheap checks —
`ruff format` had been run on `tests` after the last edit to `src`, so one file in `src` was left
unformatted and three minutes of gate found it. The pre-gate routine is both paths, always:
`ruff check src tests tools scripts` **and** `ruff format src tests tools scripts`, then the
presentation tier, then the gate.

**Gate:** `RESULT: PASS`, **4937 passed, 4 skipped** in 220s, log
`logs/ci-local-20260916-190422.log` grepped — 4 hits for the known benign set, **0** records at
WARNING or above; mypy clean on 499 source files. Test count **4936 → 4937**, measured file by file:
**−8** `test_capital_vm.py`, **−5** `test_checkbox_list_vm.py`, **−5** the `CheckboxList` half of
`test_stat_grid_and_checkbox_list_bodies.py` (8 → 3), **−2** the two pilots leaving what is now
`test_qml_overlay_load_failure.py` (3 → 1), **+14** `test_checklist_overlay.py`, **+8**
`test_capital_dialog.py`, **−1** in the guards. A net of one, for four deleted suites and two new
ones — which is what a restatement should look like.

### 4.7 PR 4.3g — the figures stop being cards, and two guards said what "no styling" means

`StatCardRow.qml` is the third rendering of the same five numbers: `EPIC-006E` drew them as
`MetricCard.qml`, `EPIC-007F` replaced that with the QtWidgets `kit.StatCard`, `EPIC-015` Phase 4
replaced *that* with a `Repeater` of `StatCard.qml`. All three were **cards** — a titled box with a
border and a background — and HLD §11.3 retires the card outright on the user's judgement
(*"các card cũ cũng rất là tệ"*), offering a read-only summary instead. `BacktestStatRow` is that:
title over figure, four across, no chrome. `.qml` **19 → 18**.

Its own file rather than another method on `BackTestTopPanel`, which is already **746 lines**
against `architecture-rule` §5's 400-line ceiling — a pre-existing violation this PR does not get to
make worse. (The panel is `screens/backtest`'s, so PR 4.4 is where it gets split.)

**Two guards decided the colour question, and neither was the styling ratchet.** ADR D21 leaves
colour only where it carries meaning and only through a `QPalette` role or a per-widget property,
and PR 0.4b had read that rule strictly for its database-status table: **no** colour at all, because
Qt has no palette role meaning *"this shard has holes in it"* and the text already said so. A profit
figure is the other case — green for gain and red for loss is a convention of this domain, not
decoration this screen invented — so the tone survives as a colour on the one label carrying the
figure.

The first draft wrote those two colours as hex literals, with a note explaining that reading them
from `Palette` would raise §11.4's `palette_files`. Two guards disagreed, in the useful way:

- `find_inline_stylesheets` fails **any** hardcoded colour outside `kit/style.py` — a number
  `EPIC-007D` drove to zero. The answer was already written: `semantic_colour()` is that module's
  documented escape hatch for *"a colour chosen per instance rather than per role"*, and its
  docstring names this exact case. It returns a token, so a palette change still reaches here, and
  it costs none of §11.4's four numbers.
- `find_bare_qt_base_widgets` caps direct `QWidget` subclasses at 2 and asks for a kit base or an
  explicit `# base-exempt:`. A row of labels is genuinely not a surface, so it carries the same
  exemption the three panels `modules/trading/ui` wrote before it — *a container, not a surface*.

Both are the shape a ratchet is supposed to have: the guard did not stop the change, it said which
of two spellings the codebase had already settled on. (A third, smaller one: ruff's `S105` reads any
`*_TOKEN = "..."` as a possible credential, so the two names are `_GAIN_COLOUR`/`_LOSS_COLOUR`.)

**Its tests were written here rather than moved, because the originals were `CS-004`'s subject.**
`StatCardRowVM`'s 8 and `StatCardRow.qml`'s 5 lived under `src/`, where the gate has never collected
them — the hole `BUG-128` cost something for. The 10 new ones restate every promise that still has a
subject; the two that do not are the QML root loading itself and the lowercase `"positive"` strings
`StatCard.qml` compared against, which existed only because a `.qml` file cannot read a Python enum.
`baseline_tests_under_src.txt` falls **22 → 19**, its first movement since 4.3d created it.

**Gate:** `RESULT: PASS`, **4941 passed, 4 skipped** in 188s, log
`logs/ci-local-20260916-192832.log` grepped — 4 hits for the known benign set, **0** records at
WARNING or above; mypy clean on 499 source files. Test count **4937 → 4941**: **+10** the new row's
suite, **−6** in the guards (the logging-namespace guard is parametrised per `src/` file and seven
went; the `.qml` style guard lost one; the new baselines account for the rest). The two host tests
that reached the old row through a QML scene now use `findChild`, and one is renamed — it was
`test_qml_renders_a_metric_card_...`, which had stopped being what it checks.

### 4.8 PR 4.3h — the second dead widget of this phase, and the two files inside it that were not

`qml/TradeLogTable/` looked like the largest step left: 827 lines, two `.qml` files, a ViewModel with
filter tabs, per-tab counts and row expansion. Measured first, as PR 3.1a's lesson requires, it is a
**deletion**: nothing in `src/` has ever loaded `TradeLogTable.qml`. The Backtest screen renders its
trades through the QtWidgets `BackTestTradeLogsPanel`, as it always has; the only thing that built
the QML one was that package's own `preview.py`. `CS-002`'s shape one level out — alive because
something *shows* it, not because anything *uses* it — and the second time this phase has found it,
after 4.3c's `DateRangeOverlay`.

Its NOTES said so in plain sight, and nobody had re-read them: *"this widget stands alone until it is
wired to a real screen"*. `EPIC-015` built the rendering and never took the last step, and the two
"additive design changes" its ViewModel documents — dropping pagination because a QML `ListView`
virtualises, and per-tab counts — are features **the user has never had**. They are recorded here
rather than carried: the live panel still paginates (`trade_log_pagination.py`, written because a
`QWidget` per row was expensive at "hàng nghìn" trades), still has no per-tab counts, and a
`QTableView` on `RowTableModel` would give it both — which is 4.4's work on that screen, not a
deletion's.

**What was not dead is the two pure files inside it.** `trade_log_row.py` (191 lines: one finished
trade as the table shows it) and `trade_log_filter.py` (60: the five tabs) are imported by four live
files in `screens/backtest/` — including `logic/trade_log_pagination.py`, which had been reaching
across into a `qml/` package since it was written. They are `screens/backtest/logic/`'s now, beside
that neighbour, and the move is what makes the package deletable at all. Both gained the module
docstring neither had, naming where they lived and why they moved.

The ten tests of `TradeLogVM` go with it, and every one of them is about the dead widget's own
behaviour (tab counts, expansion surviving a filter change, an unknown filter id ignored) — promises
of a feature that was never wired, not coverage this change drops. `trade_log_row.py` and
`trade_log_filter.py` keep their own suites in `tests/`, which only changed an import line.
`.qml` **18 → 16**, `qml_theme_refs` **152 → 123** — the largest single fall in that number this
phase, because those two files drew every cell themselves.

**Gate:** `RESULT: PASS`, **4934 passed, 4 skipped** in 210s, log
`logs/ci-local-20260916-194254.log` grepped — 4 hits for the known benign set, **0** records at
WARNING or above; mypy clean on 499 source files. Test count **4941 → 4934**: **−7**, all of it in
the guards — the logging-namespace guard is parametrised per `src/` file and five went (two moved,
so they are still counted at their new address), and the `.qml` style guard lost two. No test in
`tests/` was added or deleted: the ten that went were under `src/`, where the gate never ran them.
That is the same accounting `CS-004` predicts, seen from the other side — deleting ten tests the
gate could not see changes its count by nothing at all.

### 4.9 PR 4.3i — two more dead packages, and the pattern is now worth naming

`qml/StatGrid/` and `qml/DataTable/` are deleted without replacement: **nothing in `src/` constructs
either**. Both say why in their own notes, and neither had been re-measured since the sentence became
true.

- `StatGrid`'s NOTES: *"Duy nhất một dialog dùng: `extended_metrics_dialog.py`."* That dialog was
  replaced by `MetricsDetailPanel` — which this phase is keeping, for now — and nothing took
  `StatGrid`'s place in the graph.
- `DataTable`'s NOTES carry a banner from PR 0.4b: *"Two of the three callers are gone … so
  `TradeLogTable` is the only caller left until Phase 4 deletes `qml/` entirely."* PR 4.3h deleted
  `TradeLogTable` yesterday, which took the third.

**That is four dead QML packages in one phase** — `DateRangeOverlay` (4.3c), `TradeLogTable` (4.3h),
and these two — against three that were genuinely live and had to be rebuilt. The shape is the same
every time and it is worth stating as a rule rather than a coincidence: *a widget's last consumer
leaves, and nobody re-measures the widget.* `CS-002`'s guard catches this for bus subscribers and
`CS-003`'s for unbound ports; there is no guard for a UI component nothing constructs, and a
`preview.py` or a showcase page actively hides one by keeping an import alive. The check that would
close it is a real piece of work — it must tell "constructed by the app" from "constructed by a
gallery" — and it is recorded here rather than bolted on at the end of a deletion.

Three `.qml` go (`StatGrid.qml`, `DataTable.qml`, `_DataTablePreview.qml`), with three test files in
`tests/` whose subject went with them, and a `scanned_roots_registry.py` row for the guard that is
now gone. `.qml` **16 → 13**, `qml_theme_refs` **123 → 109**.

**Three drifted docstrings were corrected on the way out**, all of them live files making claims that
had quietly stopped being true: `kit/DialogShell.qml` listing four consumers this phase has deleted;
`MetricsDetailPanel.qml` and its ViewModel both still describing themselves as *"standalone and not
wired to a screen"*, two epics after `BackTestModalsHost` started building them. That last one is
exactly why 4.3h re-measured instead of believing a package's own notes.

**Gate:** `RESULT: PASS`, **4913 passed, 4 skipped** in 209s, log
`logs/ci-local-20260916-195706.log` grepped — 4 hits for the known benign set, **0** records at
WARNING or above; mypy clean on 499 source files. Test count **4934 → 4913**: **−13** the three
deleted files (5 + 3 + 5, every one of them about a widget nothing constructs), **−8** in the guards
(two parametrised rows per deleted `src/` file, and three for the `.qml`). Nothing was restated,
because there is no subject left to restate a promise against — the same outcome PR 3.1a's deletion
had, and the reason a deletion's test delta is allowed to be negative where a rewrite's is not.

### 4.10 PR 4.3j — the last QML dialog, and `apply_role` falls for the first time this phase

`qml/MetricsDetailPanel/` was the one live QML *dialog* left: the extended-metrics readout, opened
from the Backtest screen's metrics header. It is a `QDialog` again — `.qml` **13 → 11**, and
`src/presentation/ui/qml/` now holds nothing but `kit/`.

**Three renderings, and each one answered something.** `ExtendedMetricsDialog` drew this as a
`StatGrid` of cards. `EPIC-015` Phase 3 replaced it with `MetricsDetailPanel.qml` because the design
wanted sections, verdict badges and a profit-against-loss bar the grid could not express. This
keeps all three and drops the toolkit: HLD §11.3 maps a readout like this to *a dialog with a
table*, and a `QTreeWidget` is the platform's own "rows under headings", which is all the sections
ever were. Nothing collapses — a collapsed section would hide numbers the user opened the dialog to
read — so the tree is a table that happens to have headings in it.

**The split is the same one 4.3d made.** `logic/metrics_detail_rules.py` holds what the readout
*says*: the sections, the Sharpe/Sortino/Calmar verdicts, the drawdown duration in days, the bar's
arithmetic and the "Copy all" text — pure functions over `StatCardData`, no widget, no `QObject`.
The dialog holds the wiring. The 268-line `MetricsDetailVM` existed to re-publish every one of those
values as a `Property` for bindings to read; with no bindings, that entire layer is gone rather than
ported.

**`performance_metrics_view.py` moved with it** (357 lines, imported by the Presenter, the source
adapter and the snapshot type) into `screens/backtest/logic/` — the second file this phase has found
living inside a `qml/` package while the live screen imported it, after 4.3h's pair.

**`apply_role` moves for the first time this phase: 44 → 43, across 23 → 22 files.** Every earlier
step held it flat, because the QML packages they deleted called it from their *hosts* and those
hosts were shared. `MetricsDetailModal` was this panel's own hand-written host — a `QDialog` that
painted a `StyleRole.SURFACE` so a `QQuickWidget` scene would not render black (`BUG-115`) — so
deleting the scene deleted the reason for the call. §11.4's first number has started to fall, and it
will fall the rest of the way with `kit/`.

**Restated.** `MetricsDetailVM`'s 12 tests were under `src/` where the gate never ran them (`CS-004`,
the third such suite this phase): 11 are restated as `logic/test_metrics_detail_rules.py`'s 16, and
the twelfth — that `requestCopy`/`requestClose` emit — went with the `QObject`, its subject now the
dialog's own two buttons, which have tests. The host's 4 tests go with the host, except the
clipboard one, which is restated against the real Copy button. The screen's own 5 are restated one
for one, and the popup-overlay test that asserted on a `QVariantList` because *"the delegate carries
no per-row objectName"* now asserts on what is actually on screen.

**Gate:** `RESULT: PASS`, **4920 passed, 4 skipped** in 204s, log
`logs/ci-local-20260916-202058.log` grepped — 4 hits for the known benign set, **0** records at
WARNING or above; mypy clean on 499 source files. Test count **4913 → 4920**: **+16** the rules
suite, **−4** the deleted QML host's file, **+2** net on the screen's own dialog file (5 → 7), and
**−7** in the guards. The twelve tests that were under `src/` cost nothing on either side of this,
for the reason 4.3h's paragraph gives.

### 4.11 PR 4.3k — the timeframe picker, both views of it, and a segfault the design predicted

`support/charting/TimeframePicker/` held the **last three `.qml` files outside `qml/kit/`**: the
compact pill row in every chart header, the full grouped grid it opens, and that grid's cell. All
three are widgets now — `.qml` **11 → 8**, and every remaining one is in `qml/kit/`, the final step.

**The design's one hard requirement survived the toolkit, which is the point.** The user's
instruction shaped this widget: *"2 widget, common nếu reuse được"* — pinning an interval in one
view has to show in the other at once, so the two views share one state object rather than each
holding a copy. That is still true: `TimeframeSelection` (was `TimeframeVM`) is one `QObject` two
widgets read, with its `Property`/`Slot` decorations dropped because nothing binds to it. Its rows
are frozen dataclasses instead of `QVariantList` dicts, so `row.code` replaces `row["code"]` and a
missing field is an error where it is written rather than a `None` where it is rendered.

- `pill_row.py` — a checkable `QPushButton` per pinned code, which is what a pill is; the current
  one is simply the checked one, and the platform draws that.
- `dialog.py` — a `QTreeWidget`: headings with rows under them (what the groups always were) and a
  real check box for the pin (what a pin always was). Choosing closes; **pinning does not**, because
  pinning three intervals is a different act from choosing one.
- `chart_toolbar.py` stops being a `QuickSurface` and becomes a plain `QWidget` holding the row.
  `sig_timeframe_changed` and `set_active()` are untouched, so `ChartCard`,
  `PythonBacktestChartHost` and `dashboard_presenter.py` needed no changes at all — the third time
  this widget has been rebuilt behind that same surface.

**The segfault is worth recording, because `ChecklistOverlay` had warned about it one PR earlier.**
Ticking a pin reaches `_render()` from inside that row's own `itemChanged` emission, and the first
draft called `QTreeWidget.clear()` there — destroying the item whose signal was still being
delivered. Not a flaky test: a hard crash, and it did not appear when the file ran alone. 4.3f had
already learned this for checkboxes and written it into `set_items()`; the fix here is the same
shape, and easier, because pinning and choosing never change *which* intervals are offered: a
layout signature (group labels and their codes) decides between updating in place and rebuilding.
The lesson generalises past both widgets — **a Qt view that rebuilds itself from a signal one of its
own items raised is a crash waiting for a user to click.**

**Restated.** `TimeframeVM`'s 12 tests were under `src/` (the fourth such suite this phase, `CS-004`)
and are restated as `test_selection.py`'s 14. The deleted QML host's 7 become 12 across
`test_dialog_and_pill_row.py` — six of them one for one, the seventh (a broken `.qml` raising) gone
with its subject, plus new coverage the pill row never had of its own, because
`TimeframeToolbar.qml` was only ever exercised through `ChartToolbar`. `test_chart_toolbar.py`'s 11
wiring promises are unchanged sentences; only the click changed, from `QTest` coordinates in a Quick
scene to `QPushButton.click()`. Nine other test files across four screens swapped the same two
attribute names.

**And the first gate run failed in a tier the pre-gate routine still did not cover** — three
`tests/integration/` tests clicking a pill through `QTest` scene coordinates. That is the third time
this phase, each one a layer wider: 4.3e's was `tests/unit/presentation` above the directories I had
run, 4.3f's was `ruff format` on `src` after the last edit there, and this one is the integration
tier. The routine is now the whole of `ruff check`/`ruff format` over all four directories, then
`pytest tests/unit tests/integration`, then the gate — which is most of the gate, and the honest
price of a change that reaches widgets four screens deep.

**Gate:** `RESULT: PASS`, **4934 passed, 4 skipped** in 178s, log
`logs/ci-local-20260917-010650.log` grepped — 4 hits for the known benign set, **0** records at
WARNING or above; mypy clean on 499 source files. Test count **4920 → 4934**: **+14** the selection
suite, **+12** the dialog and pill row's, **−7** the deleted QML host's file, and **−5** in the
guards. `test_chart_toolbar.py` is 12 → 11, its broken-`.qml` test gone with the `.qml`.

### 4.12 PR 4.3l — `qml/kit/` is deleted, `.qml` reaches **0**, and five of its eight components were already dead

`src/presentation/ui/qml/` was the last QML in the application: eight `.qml` files, two Python
hosts, a `preview.py`, a `NOTES.md` and a test suite living under `src/`. All of it is gone — **`.qml`
8 → 0**, which is ADR D21 satisfied rather than merely progressed, and the point at which
`test_no_new_qml.py` stops being a ratchet and becomes a ban.

**Two widgets had to be written; the other six components had nothing left to replace.** Measuring
first (the habit §4.8 and §4.9 turned into a rule) found that `Button.qml`, `DialogShell.qml`,
`LogPanel.qml`, `PanelHeader.qml`, `StatCard.qml` and `_StyleGuidePreview.qml` had no consumer at
all: each was the shared furniture of a QML screen that an earlier 4.3 pull request had already
rebuilt, and `StatCard.qml` lost its last one to 4.3g. The kit outlived its screens by six pull
requests because `preview.py` kept every import alive — the same mechanism §4.9 named. Only the two
components a *live* QtWidgets screen was still embedding needed a replacement:

- **`kit.ProgressBanner`** (`support/ui_kit/kit/surfaces/progress_banner.py`) — a caption, a bar and
  a Cancel button, with the five setters and one signal `ProgressBanner.qml` had as properties, name
  for name, so Backtest, Data Management and Dev Board did not change a call. Built in `kit/` rather
  than in a screen because `StyledProgressBar`'s own docstring had already reasoned this out and
  declined it: *"the composite is recorded in `EPIC-007C` as a candidate; it has one instance"*.
  There are three, and the third made it shared. The percentage moves onto the bar instead of a
  label beside it — `QProgressBar` renders its own text, which is what ADR D20 asks for, with the
  format written literally so it reads 38 where Qt's own `%p` would truncate to 37.
- **`WsStatusPill`** (`presentation/ui/screens/dashboard/ws_status_pill.py`) — a dot and a label, in
  the screen's package because there is exactly one consumer. The previous version's docstring made
  the same call and named what would change it (*"revisit if a third inline `kit/` embed appears"*);
  the banner became that, this did not. Its tone vocabulary stays four words wide (idle / active /
  success / danger) rather than collapsing onto `Tone`'s three, because `Tone` has no word for
  "active" and `dashboard_presenter.py`'s `_WS_STATUS_BY_MODE` needs one.

**Two constants died with the embeds, and they were both lies about layout.** All three banner hosts
pinned the widget to a fixed 32px and the pill to 22px, because a `QQuickWidget` has no size of its
own — Data Management's constant carried nine lines explaining how the 32 had been measured
empirically. A `QWidget` measures itself, so the fixed heights are gone rather than ported;
`ui-presentation-rule.md`'s own rule against a fixed pixel height on a container holding text says
the same thing from the other direction.

**A third deletion the measurement forced: `support/ui_kit/qml_overlay.py`.** `QmlOverlay` is a
modal whose *body* is a `.qml`, so with no `.qml` under `src/` it can never have a consumer again —
and its last one, `src/presentation/ui/qml/__init__.py`, went in this pull request. Its single
guarantee (a `.qml` that fails to load raises instead of rendering a blank box) is not lost: it is
`QuickSurface`'s, asserted by the identically-named test in
`tests/unit/support/ui_kit/embed/test_quick_surface.py`, which is where the behaviour is actually
implemented.

**What is left standing, deliberately, and whose it is.** `support/ui_kit/embed/` (`QuickSurface`,
`size_policy`) now has **no `src/` consumer**: the only thing that constructs one is
`scripts/quick_surface_desktop_probe.py`, `BUG-115`'s manual probe. The theme layer
(`theme_bootstrap`, `configure_app_qml`, `Palette`, `kit/style.py`) is a different case — it still
has many live consumers — and HLD §11.4 already assigns both to PR 4.4, which retires `Palette` and
`kit/style.py` with the last `kit/` widget. Recorded here rather than removed, so 4.4 inherits a
measurement instead of a search. `tests/` keeps its own probe `.qml` files, which the ban does not
touch and should not: it scans `src/`.

**And the ceilings, measured on the files this step touched, since 4.4 moves all four.**
`architecture-rule.md` §5 rule 4 is over on `dashboard_presenter.py` (**1991** lines),
`dev_board_panel.py` (**1070**), `backtest_top_panel.py` (**723**, down from 746 here) and
`data_management_view.py` (**677**); `DashboardQmlViewModel` carries **27** public methods against a
ceiling of 15. None of it is this step's — every file it edited got shorter or stayed the same — and
the two already on 4.4's list are `dev_board_panel.py` and `backtest_top_panel.py`. The Dashboard
pair is **new to that list** and recorded here so 4.4 does not rediscover it: moving
`screens/dashboard` into `modules/*/ui` is the moment to split them, not after.

**Restated (E11), 44 deleted test functions.** The 32 under `src/` were `CS-004`'s fifth and last
such suite, and the 12 under `tests/unit/presentation/ui/qml/` went with their subjects:

| Deleted | Where its guarantee lives now |
| :--- | :--- |
| `test_progress_banner_qml.py` (5) + `test_progress_banner_widget.py` (4) | `surfaces/test_progress_banner.py` (6) — status/percent, clamping, the reversible sweep, the click, and "no stylesheet of its own". The one sentence **dropped**: the `.qml` relabelled its own Cancel button, which `kit.ProgressBanner` deliberately does not do — a button that renames itself under the cursor is not what a caller wants. **The reason first written here was wrong and §4.13 fixes it**: "two of its three callers have their own wording" is true of Backtest and false of Data Management, which lost the word entirely. The state now lives in the caption on both screens, from one shared constant |
| `test_status_pill_qml.py` (3) + `test_status_pill_widget.py` (4) | `screens/dashboard/test_ws_status_pill.py` (7) — text, four tones, three distinct colours, the hideable dot. "Loads with a real QML root object" has no subject and its place is taken by the one thing the `.qml` could not be asked: an unknown tone renders as idle rather than raising |
| `test_button_qml.py` (3) | `kit/test_controls.py` — `StyledButton` is a real `QPushButton` that accepts every button role and restyles on `setEnabled`; "a disabled button ignores clicks" is Qt's, not ours to re-test |
| `test_dialog_shell_qml.py` (6) | `kit/test_overlay.py` (title, subtitle, footer wiring, body layout) and `overlays/test_confirm_overlay.py` (confirm vs cancel) — the chrome those six described has been QtWidgets since `EPIC-007`, which is why `QmlOverlay` only ever replaced the *body* |
| `test_log_panel_qml.py` (5) | `surfaces/test_log_panel.py` (10) — badge tracking, copy and clear calling through, action labels |
| `test_panel_header_qml.py` (3) | `kit/test_style.py`/`test_surface.py` for the header's roles, `surfaces/test_log_panel.py` for a badge that hides when empty |
| `test_stat_card_qml.py` (7) | `screens/backtest/test_backtest_stat_row.py`, written in 4.3g when the figures stopped being cards (HLD §11.3) |
| `test_qml_style_discipline.py` (3) | `test_no_new_qml.py`, which is now strictly stronger: "no hex literal in a `.qml`" is implied by "no `.qml`". Its `test_there_are_qml_files_to_check` asserted a premise that is now false on purpose; what stands in for it is the `EMPTY_BY_DESIGN` row and its verifying test, which pin the emptiness as registered and intended rather than accidental |
| `test_qml_overlay_load_failure.py` (1) | `embed/test_quick_surface.py`, same test name, same `match=` string |

**Four guards needed work, and two of them are the lesson of this step.** A guard whose subject
vanishes passes faster rather than failing (PR 3.1c's finding), and emptying a scan is exactly that
shape:

- `test_no_new_qml.py` — baseline empty, docstring rewritten to say it is a ban and was a ratchet.
- `scanned_roots_registry.py` gains **`EMPTY_BY_DESIGN`**, the first exemption to "a registered scan
  must find something", because here an empty scan *is* the ADR being met. It names the exact
  (guard, root, pattern) triple, and `test_scanned_roots_are_not_empty.py` gained
  `test_an_empty_by_design_row_is_a_real_registered_scan` so the exemption cannot outlive its scan.
- `test_qml_library_does_not_import_screens.py` — its subject was `presentation/ui/qml/`. Retargeted
  to `support/ui_kit` + `support/charting` (the shared UI libraries the rule was always about) with a
  `test_the_guard_has_a_subject` of its own, and measured clean at the retarget. Same remedy PR 3.1c
  used for a rescued rule.
- `baseline_tests_under_src.txt` is **empty**: `CS-004`'s ratchet started at 22 and this is the last
  of them. `baseline_app_styling.json` goes `qml_files 8 → 0`, `qml_theme_refs 62 → 0`; the other
  five keys are untouched, as every Phase-4 step has left them.

**The first gate run failed, and this time not in a test tier.** `CS-004`'s own 35-line cap: this
pull request is what closes that case study's open count (22 unrunnable files under `src/` → **0**),
and writing that closure pushed the file to 39 lines. The rule that caught it is the case-study
directory's own — *short is the form, not a preference* — and the honest reading is the same as the
three earlier first-run failures in this phase: the pre-gate routine covers what I edited *before* I
run it, and a document edited afterwards is as unverified as code would be. Trimmed to 35, the
architecture suite back to 363 green, gate re-run on the final tree.

**Verified by breaking the line, four times (E12).** Each of the new wirings was cut and the file
run: `ProgressBanner`'s `clicked → cancelRequested` (1 failure), Dev Board's
`cancelRequested → requestStopStream` (1), Backtest's `cancelRequested → requestCancelBacktest` (1),
and Dev Board's `wsStatusChanged → _sync_ws_status` (4 — every mode row but `IDLE`, which the pill
is already in at construction). The pill's tone assertions compare renderings against a second pill
told the tone directly, rather than against a hex literal: a hardcoded expectation there would be
asserting `semantic_colour()`'s output instead of the wiring, and would pass whichever tone the
screen actually sent.

**Gate:** `RESULT: PASS`, **4922 passed, 4 skipped** in 177s, log `logs/ci-local-20260917-014700.log`
grepped — 4 hits for the known benign set (a parametrized `[ERROR]` test id twice, the log-scan
step's own two headings), **0** records at WARNING or above; mypy clean on **499** source files, one
fewer than 4.3k because `qml_overlay.py` is gone. Test count **4934 → 4922**, and the whole of the
**−12** is accounted for: **−13** in `test_logging_namespace_guard.py`, which parametrizes once per
`.py` under `src/` (15 deleted here, 2 added), **−15** the deleted `tests/unit/presentation/ui/qml/`,
**+9** `test_ws_status_pill.py`, **+6** `surfaces/test_progress_banner.py`, **+1** the registry's new
exemption test. A count that falls is worth reading twice on a pull request that deletes tests;
these five numbers are why this one is a deletion of duplicated coverage rather than a loss of it.

**PR 4.3 is complete.** Eleven steps: seven live widgets rebuilt, five packages measured dead and
deleted, one bug found (`BUG-128`) and one case study written (`CS-004`, closed here), `.qml` **27 →
0**, `setStyleSheet` 149 → 145, `qml_theme_refs` 229 → 0, and `CS-004`'s under-`src/` test ratchet 22
→ 0. Next: **4.4** — §3.12 folds 4.2a and 4.2b into it.

### 4.13 The review of 4.3l, and the one screen that lost a word

PR 4.3 was merged before this review ran, because the `pr-review` skill had been loaded once at the
start of the session and its rows applied from memory afterwards — which is the one thing that file
forbids in its own opening paragraph (*"never quote a rule from memory"*, and *"your first command
is `ls .claude/rules/`"*). Run properly against `569842d7..800d14d4`, over all **14** rule files
rather than the 7 the `CLAUDE.md` table happens to list, it found three real things. They are
recorded here rather than quietly fixed, because two of them are mistakes in what §4.12 *claims*.

**1. The gate that merged this pull request was not evidence for it.** The clause is explicit:
*"A gate run before the last commit is not evidence … Commit after the gate → run the gate
again."* `BOT-134` rewrote the rules as tagged norms while this review was running, and that clause
came through carrying `[review: B6]` — the very row it was found under, which is now the canonical
way to cite it. The PASS quoted in §4.12 ran at 01:47; five documentation files were then edited
to write that very paragraph, and the commits landed at 01:54. What had been re-run after the edits
was the static tier plus `pytest tests/unit/architecture` and the board guards — the **every commit**
row of §1's table, not the **before the pull request is offered** row. Re-run on the merged tree:
`RESULT: PASS`, 4922 passed / 4 skipped in 177s, `logs/ci-local-20260917-021018.log`, 4 hits for the
known benign set, **0** records at WARNING or above, `git status` clean.

There is a structural tension underneath it, and it is the user's call, not a rule to bend: a pull
request whose documentation quotes its own gate's numbers can never satisfy §1 in one pass. Either
every such pull request pays for two gates (~7 minutes), or §1 gains a clause naming
documentation-after-the-gate as its own case. Nothing here weakens the rule in the meantime.

**2. Data Management lost the word "Cancelling", and §4.12's stated reason was false.**
`ProgressBanner.qml` wrote it on the button itself — `text: cancelling ? "Cancelling..." :
cancelLabel` — so all three hosts got it for free. `kit.ProgressBanner.set_cancelling()` only
disables, which §4.12 justified with *"two of the three callers have their own phrasing for it"*.
Measured, that is true of exactly one: the Backtest screen sets its own caption, Dev Board never
enters the state at all, and Data Management's caption is `progressText`, which nothing updates on
cancel — `_cancel_active_work()` transitions the FSM and emits a log line. So that screen showed a
greyed button beside a caption still claiming a sync was running, and the only place the user could
read the truth was the log panel.

Fixed where the word now belongs, for both screens, from one constant:
`constants.CANCELLING_CAPTION`, beside `DATETIME_FORMAT`, which is in that file for the same reason
— two screens showing one state must not drift into two wordings. Data Management also goes
indeterminate while cancelling, because a cancel has no percentage to report. The restored guarantee
has a test on the screen that lost it, verified by breaking the line: exactly one failure.

**3. `EMPTY_BY_DESIGN` had no `Docs/VOCABULARY` row**, while the **Allowlist ratchet** row already
standing there warns in its own last column against *"a permanent exemption list"*. A new term that
needs distinguishing from an existing one is exactly what that file is for, so it has a row now
saying what it is and how it differs: it exempts one scan from the emptiness check, never from its
own rule, and a second test asserts the triple is a scan that is really registered.

Two nits went with them: `ProgressBanner.percent_text()` was a public method with **no `src/`
consumer** — five test call sites and nothing else, so it is gone and the tests read the bar, as they
already did for the caption — and two function-local imports this pull request introduced into the
integration tests moved to the top of their files (`code-quality-rule.md` §4 names test cases
explicitly, though the rule's own scope line is `src/` and `scripts/`).

**What the review confirmed, with the commands run:** scope and per-commit atomicity (the code commit
carries no `Docs/`/`Tasks/` file), no layer crossing and no new abstract method, every file the step
edited shorter or unchanged, no `sleep` and no new hand-written double, six break-the-line checks
(the four in §4.12 plus two this review added on the new registry exemption — a bogus row fails, and
removing the early return makes the `.qml` scan fail, so the exemption is load-bearing rather than
dead code), the styling ratchet only falling, `preview.py` present, no new logger,
`SPEC-002`'s *Proven by* row still naming a file that exists and a promise this step kept, and the
skill-reference checker clean.

**What nobody has checked is pixels.** `setTextVisible(True)` on the banner's bar is a visual change
verified only through the QSS (`style.py`'s `PROGRESS` role already sets `color: textPrimary` and
`text-align: center`, so the role was written for a bar that shows its text) and through offscreen
tests. It wants one look on a real desktop, which is the user's run, not the gate's.

### 4.14 `BUG-129` — and GitHub CI had been red since PR 3.1c, not since 4.3j

Reviewing 4.3l was what surfaced it, but the defect belongs to this phase's whole run of merges,
so it is recorded here. Another session's commit (`9a4a65d2`) reported that
`scripts/check_skill_prompt_references.py` had been failing in CI since 2026-09-16 20:26 across
three runs, and deleted the two agent briefings whose cited paths `EPIC-025`'s moves had removed.
Two things about that turned out to be worth measuring rather than accepting.

**The local gate had been calling that same step green** — on this machine it printed *"OK: every
repository path ... resolves"* while CI failed it. The reason is the whole bug: `check()` resolved
every reference with `Path.exists()`, which answers about the disk it runs on. `EPIC-025`'s moves
left the two directories those briefings cite behind as shells holding nothing but `__pycache__`,
and nothing deletes those. Gone from the repository, present in every working tree. So the
briefings were the symptom, and the mechanism is a check whose answer depends on who runs it —
worse than no check, because it is believed. It reads `git ls-files` now.

**And the red is older and longer than the commit says.** Read from the runs themselves rather
than inherited: the last green is run **370** (14:21 UTC), and red starts at **371**, 14:49 —
the merge of PR 3.1c's own documentation, the pull request whose message states *"`src/application/`
is empty and gone from disk"*. Every completed run from 371 to 390 failed: **20 runs, about 11½
hours**, the four that closed PR 4.3 among them. Runs 371, 386 and 390 were read directly.

**The two halves were queued behind each other.** Once the briefings were deleted, run 390's
reference check passed, pytest ran for the first time in 20 runs, and it failed on
`test_module_boundaries.py::test_src_root_is_where_we_think_it_is` — *zone `application` missing* —
the second instance of the identical disease, found here twenty minutes earlier by cleaning the
stale directories off this disk. That guard's `_ZONES_THAT_MUST_EXIST` required a directory the
epic had deleted, so it had been passing everywhere for the same wrong reason, and the first
failure hid it by failing before pytest could run. Retired with the reason in place; `domain`, now
one file, is flagged as the next.

Written up as [`CS-005`](../../../Docs/CASE_STUDIES/CS-005_the_check_that_asked_the_wrong_question.md)
with `BUG-129`'s report. What it does **not** close is the habit underneath: nothing in the local
workflow reads CI's verdict for the branch it just pushed, which is why a green local gate and a
red remote could coexist for half a day. Reading it is a step, not a tool, and this phase is the
evidence for taking it.

### 4.15 The review of 4.3d–4.3k, run against the rule files

§4.13 admitted that the eight steps before 4.3l had their checklist applied from memory rather
than from the rule files. This is that review, run properly over `3444cee0^..2266fdd6` — 16
commits — and it found two things plus one measurement error of its own.

**1. A fixed pixel width on something that holds text** (`capital_dialog.py`, PR 4.3f).
`ui-presentation-rule.md` allows a fixed size only for a true leaf glyph — *"never a fixed pixel
size on a container holding text or widgets (a leaf glyph may)"*, now tagged `[review: H4]` — and
the consequence for anything else is a clip at another DPI or in another locale, because a
localized string can run longer than its English source. The currency `QComboBox` carries codes, and it was `setFixedWidth(90)`. The row is the
amount field at stretch 1 beside a combo with no stretch, so a **floor** gives the same layout
today and grows instead of clipping: `_CURRENCY_MIN_WIDTH` and `setMinimumWidth`. Pinned by a test
that reads `maximumWidth()` — a `setFixedWidth` sets minimum and maximum to the same number, so
putting one back fails it. Verified by putting one back: exactly one failure.

**2. PR 4.3h left two live modules named `trade_log_row`** — the row *widget*
(`screens/backtest/_trade_log_row.py`, there since PR 1.6a) and the row *as the table shows it*
(`screens/backtest/logic/trade_log_row.py`, added by 4.3h). Both are imported by the live screen,
so neither is dead; what is wrong is that the name no longer says which. Deliberately **not**
renamed here: PR 4.4 moves this whole screen into `modules/backtesting/ui/`, and a five-importer
rename now is churn against a file that is about to move anyway. Recorded so that move does it.

**3. The review's own first measurement was wrong, and the way it was wrong is worth keeping.**
`baseline_tests_under_src.txt` compared across the range read **0 → 8**, which would be a ratchet
growing — `ci-rule.md` §5.5's blocking case. It is not: `git show <before>:<path>` on a file that
did not exist yet prints nothing, and `wc -l` of nothing is 0. The file was *created* by 4.3d at
22 entries and shrank 22 → 19 → 16 → 14 → 11 → 8 across the range. Reading it per commit is what
said so. A diff against a commit where the file was absent cannot be read as a count.

**What the review confirmed, with the commands:** every ratchet fell or held flat (`qml_files`
22 → 8, `qml_theme_refs` 166 → 62, `apply_role` 44 → 43 across 23 → 22 files, `setStyleSheet`
145/21 unchanged, the boundary allowlist 58 → 58); 11 test files under `tests/` and 23 under `src/`
deleted with **zero** skips or `xfail`s added anywhere in the range; all eight epic sections
§4.4–§4.11 and all eight `TRACKING` status rows present; `test_spec_index_is_consistent` green, so
no `SPEC` cites a test the range deleted; 4.3h's own E11 claim spot-checked against the tree (the
four `trade_log_*` files in `logic/` really are imported by the panel, the coordinator and the
presenter); no `hasattr`/`getattr` probing added, no `logger.info` in a hot loop, no new
`@safe_ui_action` slot; and the four files still over the 400-line ceiling
(`backtest_presenter.py` 1819, `dev_board_panel.py` 1070, `backtest_top_panel.py` 726,
`data_management_view.py` 691) all predate the range and are already on PR 4.4's split list.

**Footnote, written after the fact.** `BOT-134` merged into `master-warrior` between this review's
last check and its merge: the twelve rules rewritten as norms, 1 976 → 453 lines, `qml-rule.md` and
`code-rule.md` deleted, and an enforcer tag on every clause. Both findings above were re-checked
against the rewritten files rather than assumed to survive — every clause this review cited is
still there, and each now carries the `[review: …]` row it was found under, `B6` and `H4`
included. The reference checker `BUG-129` had just taught to read `git ls-files` is what confirmed
the rewrite left no dangling path behind it: **11 documents, every path resolving**, on the merged
tree.

### 4.16 A second session's review of §4.15 (PR #223), and what it found still open

`ONBOARDING.md` §7 requires a different session to review before code reaches `master-warrior`;
PR #223 got one. No blocking findings — the code was sound — but four should-fix and two nits,
and two of the four are worth recording here because they are not typos: they are the same class
this whole review cycle exists to close, caught a level up.

**S1 — `CS-005` struck through a class that was still open, and the strikethrough was wrong on a
live instance, not just on a hypothetical one.** The reviewer reproduced `BUG-129`'s exact shape
on `test_module_boundaries.py`'s zone check: `git rm --cached` the one file `domain` tracks, leave
the directory (and its `__pycache__`) on disk, and `test_src_root_is_where_we_think_it_is` kept
passing — `is_dir()` cannot tell a zone still holding real files from one surviving only as a
stale shell, exactly the shape that let `application` sit in `_ZONES_THAT_MUST_EXIST` for 14
hours after the repository had nothing left under it. Fixed the same way: the check now asks
`git_tracked_paths.tracked_paths()` for at least one file under each zone. That helper is new too
— it did not exist when §4.15 was written; there were **two** independent copies of the same
`git ls-files` logic (the script's, the registry's), and writing a third for this check would have
been the exact drift `CLAUDE.md`'s opening warning names. All three guards (the script keeps its
own, since it must not import `tests/`; the registry; the zone check) now read from one place.
`CS-005`'s strikethrough is un-struck, with a new row for the mistake itself: closing the *class*
after fixing one instance, when a second lived in the same shape, is the failure a case study
exists to catch, and it caught its own.

**S2 — the registry's `_tracked_paths()` returned `None` and skipped the filter with no warning,
unlike the script's own `check()`, which prints one naming `BUG-129`.** `git_tracked_paths.py`
carries that warning now, in the one place both callers reach it.

**S3 — "Architecture tier: 386 passed" in the PR body was a number this disk produced, not one the
repository does.** The reviewer reproduced 380 on the same head; the discrepancy is
`test_claude_rule_pointers_match_agents_rules.py`, which parametrizes from `.agents/rules/` and
`.claude/rules/` **on disk** — and `BOT-134`'s merge, landing mid-review, had deleted `qml-rule.md`
and `code-rule.md` from the repository while an earlier `ruff`/pytest run of mine had left them on
this container's disk. The number in the PR body is corrected to the reproducible one.

**S4 — the cited gate log did not run on the head commit.** `cdfdffd3` is documentation-only, so
`ci-rule.md`'s exception covers it, and GitHub CI ran the full gate on that exact head and passed
(run 397) — but the PR body should have cited that run for the head commit and the local log only
for its parent, not one log for both. Corrected in the PR body.

**N1 — the fix was scoped to the one regression, and the deferral was not written down.**
`src/` carries eleven more `setFixedWidth`/`setFixedSize` calls the reviewer listed by file and
line, several on text-holding widgets (`backtest_trade_logs_panel.py`'s search field,
`settings_view.py`'s save button and sync-days spinner, `gap_inspector_dialog.py`'s close button).
Left alone deliberately: fixing eleven call sites nobody asked about, while reviewing a fix for
one, is the scope creep `pr-review` row A1 exists to catch from the other direction. Recorded here
as the list for whoever next touches the H4 clause, rather than fixed as a side effect of this PR.

**N2 — `BUG-129` had no line in `Tasks/ROADMAP.md`.** Added, at the top of `🟢 Completed`, per
`ONBOARDING.md` §6.

### 4.17 A third session's review, and the S2 fix it found still silent

A third independently-spawned session re-verified §4.16's fixes rather than trust the commit
messages, and reproduced every break-the-line probe itself. No blocking findings; one should-fix,
worth recording for the same reason S1 was: it is the same *class* of defect one level over again.

**S2's own fix — `warnings.warn()` naming `BUG-129` when git cannot answer — fires, but is
invisible to both mechanisms this repository actually uses to detect a failure.** `CLAUDE.md`'s
mandated `grep -nE "FAILED|ERROR|Traceback|ResourceWarning"` does not match a pytest
warnings-summary line, and `ci-local.ps1`'s `Invoke-RunLogScan` greps the structured
`- (WARNING|ERROR|CRITICAL) -` app-log format, not pytest's own output. Reproduced: `git` removed
from `PATH`, both guard files finished `130 passed, 81 warnings`, exit 0 — the exact silent green
`BUG-129` exists to close, wearing a warning as a costume. Fixed by removing the warning entirely:
`git_tracked_paths.tracked_paths()` now raises `GitUnavailableError` instead of returning `None`,
so a caller's own test fails rather than skipping its filter — pinned by the new
`tests/unit/architecture/test_git_tracked_paths.py` (5 tests, two of them E12 breaks against the
real guards, not just against `tracked_paths()` in isolation). `CS-005` and `BUG-129`'s own report
carry the addendum.

This makes three independent sessions finding a live instance of the identical shape — the
filesystem-vs-repository disagreement, or its silence — at three different points in the same
mechanism (a script, then two test guards, then the warning meant to cover both). The pattern
itself is now the lesson worth naming: a fix for a *silent* failure mode should be verified by
trying to make it fail silently again, not by confirming the new code path runs.

**What the reviewer confirmed, independently, in a fresh container:** installed the toolchain
itself rather than trusting the PR's claim that one existed; ran the full gate and got the same
pass/fail shape; ran the registry's own break-the-line probes and the two new ones above, all
producing exactly the failure named; read the GitHub CI run for the head commit rather than taking
the PR body's word for it; and restored every probe, leaving `git status` and `git diff HEAD`
both empty when done — the housekeeping this whole review chain has been asking every step to do.
