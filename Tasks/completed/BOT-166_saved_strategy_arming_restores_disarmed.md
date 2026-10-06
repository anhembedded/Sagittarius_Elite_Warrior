# BOT-166 — A saved strategy arming is restored at start as disarmed; the user re-arms it explicitly

**Status:** ✅ Done (2026-10-06)
**Board:** Decision (owner, 2026-10-06): a saved strategy is restored at start as a selection, never armed — boot's re-arm is deleted, the Bots row shows "Saved, not armed" with the settings, and one Arm action in the session arms it; no tick reaches an engine before. No conflict with `EPIC-026` O2/`026H` (those adopt positions on enable).
**Source:** `BUG-163` (PR #398) found a saved strategy re-armed at boot. The owner (2026-10-06), accepting the coordinator's safer option: *"như bạn đề xuất"* — restore the saved configuration so re-arming is one action, but do not arm it.
**Risk:** 🟡 — removes the boot-time arm on the live-trading path; the failure to guard is the opposite one (a restore path that quietly arms again).
**Complexity:** S — one boot step deleted, one UI row field added; the weight is the proof on the composed app.
**Epic (optional):** [`EPIC-026`](../epics/EPIC-026_road_to_real_money/README.md) (principles only; no child task changes)
**SPEC (optional):** [`SPEC-004`](../../Docs/SPEC/SPEC-004_enable_and_disable_live_trading.md) §6 and §8 (`SPEC-010`, arming's own SPEC, is still reserved for `EPIC-026C`; it inherits the rule).
**Depends on:** None

---

## 1. Context and problem

`StrategyModule._restore_armed_strategies` (`src/modules/strategy/module.py:277`) called `IStrategyArming.arm()` for each enabled venue's saved configuration during `boot()`. A strategy the user armed last week was therefore live on the first tick after a start the user did not confirm in that session (`BUG-163` follow-up, owner decision of 2026-10-06). Real money makes "armed by yesterday's click" the wrong default: the market, the account and the venue key may all have changed.

### Check against `EPIC-026` (ADR, O2, crash recovery, `EPIC-026H`) — no conflict
- ADR `O2` and `EPIC-026H` are about a **position** the journal recorded as ours: adopted on *enable* (`SPEC-004` §3 step 5), matched by `(venue, symbol, side, quantity)`. They adopt exchange state; they never arm a strategy engine, and `EPIC-026H`'s "symbol lease re-claimed for the journaled owner" is the lease, not the engine.
- This task restores a **configuration**, and arms nothing. After a crash with an adopted position the user re-arms (one action, same symbol, which claims the lease); `EPIC-026H` should state that order when it is built (arm needs trading OFF, adoption happens on enable) — a note for that task, not a change to it.
- Neither rule depends on a boot-time arm.

## 2. Acceptance criteria
- [x] With a complete saved arming for an enabled venue, the composed app starts with that venue's strategy **not armed** (`IArmedStrategyReader` reports none; no `LiveStrategySession` has an engine).
- [x] The Bots mode shows that venue as `Not armed` and shows its saved selection (strategy, symbol, interval, sizing, leverage, parameters) on the row.
- [x] One Arm strategy… action (Bots menu → dialog answered Arm) arms it with exactly the saved settings.
- [x] No market tick reaches a strategy engine before that action; after it, a closed tick for the armed symbol and interval does.
- [x] A saved configuration is still kept (`LiveStrategyConfigStore`): restoring never rewrites or clears it.
- [x] The arming SPEC text states the rule.

## 3. Design
The boot step is deleted, not flagged: a `restore_armed=False` switch would leave the arming door open at boot for the next caller. `_restore_armed_strategies` keeps only `adopt_legacy` (moving a single-venue app's unscoped keys to their venue), renamed `_adopt_saved_selection`; the saved selection already reaches the form through `IStrategyArming.saved_selection()` → `StrategyArmingCoordinator.restore_into_view_model` (it "does nothing else", `BUG-101`/`BUG-104`). `_arm_from_config` and its test are removed with it; the validated door's own coverage stays in `test_arm_strategy.py` and `test_strategy_arming_contract.py`.

The Bots row gains `saved` (the saved selection in words, empty when none is complete); `Not armed` stays the state word, so a saved selection can never read as a running strategy.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/strategy/module.py` | `boot()` no longer arms; only the legacy-key adoption stays |
| `src/modules/bots/ui/strategies/strategy_rows.py`, `venue_strategies.py` | Row shows the saved selection of a disarmed venue |
| `Docs/SPEC/SPEC-004_enable_and_disable_live_trading.md`, `Docs/VOCABULARY/README.md` | The rule: a start never arms (SPEC §6, §8; the vocabulary row said boot re-arms) |
| `tests/unit/modules/strategy/test_module_boot_arming_reuses_the_validated_door.py` | Deleted with `_arm_from_config` (its subject) |
| `tests/unit/modules/strategy/test_module_restores_each_venues_strategy.py` | Rewritten: boot arms nothing, keeps the saved keys, still adopts legacy keys |
| `tests/integration/presentation/ui/test_saved_strategy_restores_disarmed.py` | New: the composed app, the four proofs |

## 5. Testing
Integration tier on the real composed app (fake Binance server), mutation-checked: restoring the boot arm turns the first, second and fourth red. Unit: the rewritten boot test. Commit tier per `ci-rule.md` §1; `-Full` is GitHub Actions'.

## Implementation notes (written when done)
- **Red first, for the right reason:** on the unchanged boot the composed app reported `ArmedStrategyConfig(... ETHUSDT 5m ...)` armed with `engine_running=True` and the row read `Ema Crossover · ETHUSDT 5m ...` as armed.
- **Mutation checks** (run on `test_saved_strategy_restores_disarmed.py` + `test_module_restores_each_venues_strategy.py`): boot re-arming → 6 red (all four composed-app tests, two unit); the row hiding the saved selection → the "shows it not armed with its settings" test red; the Arm action not filling the form from the saved selection → the "one arm action arms exactly what was saved" test red.
- **Deleted, not replaced:** `test_module_boot_arming_reuses_the_validated_door.py` guarded `_arm_from_config`, which no longer exists. The door it protected (the Spot-only refusals through `ArmStrategyCommandHandler`) is covered at the handler: `test_arm_strategy.py::test_spot_refuses_a_strategy_that_can_short` and `test_arm_strategy_per_venue.py::test_spot_still_refuses_a_short_capable_strategy_that_futures_accepts`.
- **Shared helper:** `trade_mode_boot.trade_mode_running` takes an optional `user_config` and its `TradeDesk` now carries the `container`; both are additive.
- **Note for `EPIC-026H`:** after a crash with an adopted position the user re-arms the symbol first (arm needs trading OFF), then enables; adoption on enable should expect the lease may already be claimed by that arming. Not changed here.
- **Verified:** `ci-local.ps1 -SkipTests` PASS (`logs/ci-local-20261006-165356.log`); `tests/unit/architecture`, `tests/unit/modules/strategy`, `tests/unit/modules/bots`, the Trade-mode and Bots-catalogue integration files and the new one: 1734 passed. Not run locally: the `-Full` gate (GitHub Actions').
