# EPIC-025E — Phase 4: `support/{charting, indicators, ui_kit}`; dissolve `presentation/ui/common/`

- **Status:** 🔴 Backlog
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
   generic indicators package. **Open for the user**, same shape as `sync_progress_*` in step 3,
   and the pair stays where it is until then.
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
   the epic promised, so it is **open** and needs the user's call; until then the pair
   stays where it is and nothing is moved quietly. What remains for *this* phase is whatever still has a legacy
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
   deletions in this step instead. Concretely: once step 3 has emptied `ui/common` and the QML
   packages are gone, `screens/trading` and `screens/dashboard` `git mv` into
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
