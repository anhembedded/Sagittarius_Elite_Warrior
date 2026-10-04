# BOT-148 — Every contribution defers its factories through `Deferred`, and the PLC0415 ratchet loses 32 hits

**Status:** 🔵 Backlog
**Source:** PR #333 review, finding 2 (2026-10-04). The user delegated the decision: "dựa vào hiến pháp mà quyết" ("decide by the Constitution"). Decision: P8 forbids a new baseline line, and P6 says to fix the mechanism, so `Deferred` was built and the Bots screen uses it. This task moves the remaining contributions onto it.
**Risk:** 🟡 — a mistyped target fails only when its screen first opens; `test_deferred_targets_resolve.py` catches that for module contributions, but not yet for the shell's own screens.
**Complexity:** M — ten files; two screens close over a container, so their factories need a different shape.
**Depends on:** PR #333 (`src/core/contracts/deferred.py`, `tests/unit/architecture/test_deferred_targets_resolve.py`) merged.

---

## 1. Context and problem
Every lazy contribution defers with function-local imports, one `PLC0415` hit per factory. `tests/unit/architecture/baseline_ruff_debt.json` counts them: `backtest_screen.py` 4, `database_screen.py` 3, `market_data/ui/settings_contribution.py` 2, `watchlist_screen.py` 3, `dashboard_screen.py` 3, `desk_factories.py` 7, `trading/ui/probes.py` 2, `trading/ui/settings_contribution.py` 2, `shell/settings/settings_screen.py` 3, `shell/welcome/welcome_screen.py` 3. That is 32 hits. `Deferred` (PR #333) replaces the import statement with one `importlib` call in a single file.

## 2. Acceptance criteria
- [ ] Each file above defers through `Deferred`; its `PLC0415` line leaves `baseline_ruff_debt.json`.
- [ ] `test_deferred_targets_resolve.py` also walks the shell's own screens (`welcome_screen()`, `settings_screen()`), holding each target inside `src/shell/`.
- [ ] `test_module_contribution_laziness.py` stays green, including the headless subprocess check.
- [ ] `code/quality.md` §2 drops the clause that counts a laziness-required import among the hits, once none remain.

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
