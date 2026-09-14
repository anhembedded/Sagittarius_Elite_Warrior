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
