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
| **4.1a** | `components/order_book` (7 files) → `modules/trading/ui/` | 0 legacy imports; its outbound reads are `modules/trading/contracts` (×9) and `support/ui_kit` (×3), all legal from a module's `ui/`. The 1.6a shape: a clean leaf, zero allowlist either way |
| **4.1b** | the seven `trading`-owned `ui/common` feeds → `modules/trading/ui/` | after 4.1a, their only legacy read is `order_book`, which will already be in the module |
| **4.1c** | `screens/trading` (9 files) → `modules/trading/ui/`; the duplication criterion starts falling | after 4.1a/b its legacy-import count is **0** |
| **4.2a** | `sync_progress_{feed,report}` → `modules/market_data/ui/`, with `symbol_options_coordinator` | §3.3 below: the destination this file left open is **forced**, not chosen |
| **4.2b** | `screens/data_management` → `modules/market_data/ui/` (step 6, inherited from Phase 0) | after 4.2a, its remaining three are QML, so it waits on 4.3 |
| **4.3** | the QML deletions (ADR D20–D21): the backtest screen's eleven modals become `QDialog`s and its panels docks, `qml/` is deleted, `find src -name '*.qml'` → 0 | the one step with real UI work in it, and the only one the user sees |
| **4.4** | `screens/backtest` → `modules/backtesting/ui/`; `screens/dashboard`; `ui/common` deleted; `binance_bot_module.py` deleted; settings becomes a surface | every remaining blocker is 4.3's |

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
