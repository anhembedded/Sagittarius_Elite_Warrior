# BOT-148 — Every contribution defers its factories through `Deferred`, and the PLC0415 ratchet loses its hits (9 in the end: 32 was the count when the task was written)

**Status:** ✅ Done (2026-10-19)
**Priority:** P3
**Board:** Seven of the ten contributions had already moved onto `Deferred` and the Welcome and Settings screens were gone; the last three (Backtest and Database screens, the trading session probe) now defer through it, `Deferred.bind` carries the Backtest view's container, the ratchet lost 9 `PLC0415` hits, and the deferred-target guard also walks the shell's own screen.
**Source:** PR #333 review, finding 2 (2026-10-04). The user delegated the decision: "dựa vào hiến pháp mà quyết" ("decide by the Constitution"). Decision: P8 forbids a new baseline line, and P6 says to fix the mechanism, so `Deferred` was built and the Bots screen uses it. This task moves the remaining contributions onto it.
**Risk:** 🟡 — a mistyped target fails only when its screen first opens; `test_deferred_targets_resolve.py` catches that for module contributions, but not yet for the shell's own screens.
**Complexity:** M — ten files; two screens close over a container, so their factories need a different shape.
**Depends on:** PR #333 (`src/core/contracts/deferred.py`, `tests/unit/architecture/test_deferred_targets_resolve.py`) merged.

---

## 1. Context and problem
Every lazy contribution defers with function-local imports, one `PLC0415` hit per factory. `tests/unit/architecture/baseline_ruff_debt.json` counts them: `backtest_screen.py` 4, `database_screen.py` 3, `market_data/ui/settings_contribution.py` 2, `watchlist_screen.py` 3, `dashboard_screen.py` 3, `desk_factories.py` 7, `trading/ui/probes.py` 2, `trading/ui/settings_contribution.py` 2, `shell/settings/settings_screen.py` 3, `shell/welcome/welcome_screen.py` 3. That is 32 hits. `Deferred` (PR #333) replaces the import statement with one `importlib` call in a single file.

## 2. Acceptance criteria
- [x] Each file above defers through `Deferred`; its `PLC0415` line leaves `baseline_ruff_debt.json`. (Seven had already moved by the time the task started; the three that remained are done.)
- [x] ~~`test_deferred_targets_resolve.py` also walks the shell's own screens (`welcome_screen()`, `settings_screen()`)~~ Adapted: those screens no longer exist; the guard walks `developer_screen()`, the only shell screen left, holding its targets inside `src/shell/` (see the notes).
- [x] `test_module_contribution_laziness.py` stays green, including the headless subprocess check.
- [x] ~~`code/quality.md` §2 drops the clause that counts a laziness-required import among the hits~~ Adapted: reworded, not dropped, because one laziness-required import remains outside a contribution factory (`strategy_chart_overlay_service.py`); it now says every contribution defers through `Deferred`.

## 3. Design
- Screens with argument-free factories (`database`, `watchlist`, `settings`, `welcome`, `probes`, the settings contributions) take a `Deferred` per factory, as `bots_screen.py` does.
- `dashboard_screen(container)` and `backtest_screen(container)` close over the container. One option is to pass it at call time, since the shell's presenter factory already receives `container`. If a factory truly needs it earlier, the other option is a `Deferred` that binds leading arguments (`Deferred(target).bind(container)`). Choose between them from the code; do not build both.
- `desk_factories.py` builds two desks from one parameterised factory; fold the venue into the target or a bound argument.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| The ten files above | Factories become `Deferred` targets |
| `tests/unit/architecture/baseline_ruff_debt.json` | Each file's `PLC0415` line removed |
| `tests/unit/architecture/test_deferred_targets_resolve.py` | Also walks the shell's screens |
| `.claude/rules/code/quality.md` | §2 clause updated when the last hit goes |

## 5. Testing
Unit: `tests/unit/architecture` (ratchet, laziness, deferred targets) and `tests/unit/shell/test_screen_wiring.py`. Sanity: the real boot opens every route (`tests/sanity`). Mutation: a mistyped target in one migrated screen turns `test_deferred_targets_resolve.py` red.

## Implementation notes (written when done)
The task's list was out of date by the time it started: `watchlist`, `dashboard`, `desk_factories`, both settings contributions, `settings_screen` and `welcome_screen` no longer hold a function-local import (the screens were removed or already migrated, `EPIC-033C`, `EPIC-033E`, `EPIC-033P`), so the ratchet held 9 contribution hits in 3 files: `backtest_screen.py` (4), `database_screen.py` (3), `trading/ui/probes.py` (2). Those are migrated:
- `database_screen.py` names the view and presenter classes (`bots_screen.py`'s shape); the isinstance guards that only narrowed `BaseView` for mypy are gone with the local imports.
- `backtest_screen.py` needs the container at view construction (the config-driven view choice, `EPIC-013F`): its two factories are now `ui/screen_factories.py` (`build_backtest_screen_view`, `build_backtest_screen_presenter`, which keep the concrete-type checks), and the view factory is `_VIEW.bind(container)`. `Deferred.bind` was the task's second option; it was chosen over passing the container at call time because `PresenterManager.navigate_to()` calls the view factory with no argument, and over a closure because a closure hides the target from the guard.
- `probes.py` now holds only the `Deferred` (`TRADING_SESSION_PROBE`); `build_trading_session_probe` moved into `session_probe.py` (the widget module itself, imported lazily). `trading/module.py` sits at exactly the 400-line ceiling, which is why the constant lives in `probes.py` and not in the module.
- `test_deferred_targets_resolve.py` walks `developer_screen()` too (the only screen the shell contributes now), holding its targets inside `src/shell/`; a mistyped Backtest target turns it red (checked). `baseline_ruff_debt.json` loses the three entries.
- `code/quality.md` §2: the clause could not be dropped, since one lazy import that `test_module_contribution_laziness.py` requires remains outside a contribution factory (`strategy_chart_overlay_service.py`); it now says every contribution defers through `Deferred`.
