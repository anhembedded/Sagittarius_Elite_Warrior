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
| **4.3** | the QML deletions (ADR D20–D21): the backtest screen's eleven modals become `QDialog`s and its panels docks, `qml/` is deleted, `find src -name '*.qml'` → 0 | the one step with real UI work in it, and the only one the user sees |
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
