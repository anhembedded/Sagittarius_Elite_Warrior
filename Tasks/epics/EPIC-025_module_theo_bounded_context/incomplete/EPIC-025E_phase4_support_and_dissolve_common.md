# EPIC-025E — Phase 4: `support/{charting, indicators, ui_kit}`; dissolve `presentation/ui/common/`

- **Status:** 🔴 Backlog
- **Repository:** Elite
- **Blocked by:** D · **Blocks:** F
- **Read first:** HLD §2.3 (a support package is not a bounded context: no business language, no
  business rules allowed), §3.4; ADR D6 (the per-module QML question is reopened here).

## 1. What to do

1. `support/charting/` ← `components/chart_card` (QtWidgets, permanently) plus `IChartHost` and
   the marker / region / info types in `contracts/`.
2. `support/indicators/` ← `domain/indicators`, `indicator_scripts`, `scripting`, plus
   `IIndicatorCatalog`.
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
   import `support/**` whole. Done so far: `assets/` (PR 1.6a — `Palette`, `IconLoader`, the
   Lucide icon set and the boot preflight), `kit/` (PR 1.6b — 28 files, which
   `assets/` leaving had turned into a leaf) and six of the `ui/common` helpers above
   (PR 1.6c — `action_ownership_tracker`, `app_defaults`, `base_feed` and the three
   `health_*` files). Re-measured after each cut, which is what decides the next one
   rather than the order this list was first written in: `components/sidebar` (9
   files) and `components/environment_banner` (3) are leaves now, `qml/embed` (3) and
   `constants.py` (1) always were, and `qml/kit` (13) plus `qml/DataTable` (5) depend
   only on `kit` and `qml/embed`. `components/market_picker` does **not**: it depends
   on `qml/SelectList`, which this phase deletes rather than moves — and the same
   argument applies to the two `qml/*` rows themselves, which ADR D21 deletes in this
   phase, so moving them first is work done twice. Then
   `services/display_timezone_service.py`.

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
