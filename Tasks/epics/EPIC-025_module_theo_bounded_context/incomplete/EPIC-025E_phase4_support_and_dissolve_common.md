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
| **4.2a** | `sync_progress_{feed,report}` → `modules/market_data/ui/`, with `symbol_options_coordinator`; `base_event_logger` → `modules/backtesting/ui/` | §3.3: the destination this file left open is **forced**, not chosen. All four have 0 legacy imports except `sync_progress_feed`, whose only one is the sibling travelling with it |
| **4.2b** | `screens/data_management` → `modules/market_data/ui/` (step 6, inherited from Phase 0) | after 4.1b and 4.2a its remaining blockers are QML, so it waits on 4.3 |
| **4.3** | the QML deletions (ADR D20–D21), in sub-steps — §4 measures them: **4.3a** ✅ the shared symbol picker becomes virtualised, **4.3b** ✅ `qml/SymbolPicker/` deleted, **4.3c** ✅ `DateRangeOverlay` deleted (dead), **4.3d** ✅ `qml/TimeRangePicker/` → `support/ui_kit/time_range_picker` on `QCalendarWidget` (`BUG-128`, `CS-004`), **4.3e** ✅ `qml/SelectList/` deleted, its four hosts onto `kit.PickerOverlay` (and the read-only one out of the picker shape altogether), **4.3f** ✅ `qml/CheckboxList/` + `qml/Capital/` deleted — `kit.ChecklistOverlay` arrives for the two checklists, and the capital form keeps `BUG-064`'s lesson with one writer instead of three bindings, then `MetricsDetailPanel`/`StatCardRow`/`TradeLogTable`, `DataTable`/`StatGrid`, `charting/TimeframePicker`, and `qml/kit/` last. `find src -name '*.qml'` **24 → 19**, and → 0 when they are all gone | the one step with real UI work in it, and the only one the user sees |
| **4.4** | `screens/backtest` → `modules/backtesting/ui/`; `screens/dashboard`; `ui/common` deleted; `binance_bot_module.py` deleted; settings becomes a surface | every remaining blocker is 4.3's |

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
down in the place that promised it: HLD §3.5's row is corrected with 4.2a.

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
