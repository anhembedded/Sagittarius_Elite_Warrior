# BUG-187 — A reconcile empties the level of an order that ended without filling and never re-lays it

- **Reported:** 2026-10-08 (found by the `EPIC-035B` session while writing the gap reconcile; not reported by a user)
- **Severity:** 🟡 P2 — a hole in a running grid: one level stays empty until the bot is stopped and started again, so the grid earns nothing there. No money is at risk and no order is wrongly placed.
- **Status:** ✅ Fixed (2026-10-08)
- **Board:** A reconcile (after a restart, and after every stream reconnect) dropped a saved order that was no longer open and had executed nothing, and its level stayed empty. Cause: `GridReconciler._apply_missed_fills` ended every missing order with `drop_order`, which empties the level and re-places nothing, where the stream's end event runs `on_end`. Fix: a missing order that is not whole now runs `on_end` (re-placed once, held like a counter order; `LEVEL_KEEPS_ENDING` halts), in both entry points.
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) → bots (`src/modules/bots/`) → `application/services/grid_reconciler.py`
- **Environment:** Linux container; `master-warrior` `546b8a3` with the `EPIC-035B` branch; unit tier, simulated venue. Not seen on an exchange.

## Reproduction
1. A RUNNING Grid with its four orders resting (`tests/unit/modules/bots/application/services/gap_world.py::running`).
2. The BUY at 110 is cancelled on the exchange's website while the user-data stream is down: it leaves the open orders and history shows no execution.
3. The stream reconnects, or the periodic check comes due, and `executor.reconcile_after_gap()` runs. The same happens for a RECOVERING bot at `GridReconciler.run()`.

Expected: the level is laid again once, as `GridExecutor._apply_end` does when the stream reports the cancel (`grid_reactions.on_end`).
Actual: observed with a scratch test on the `EPIC-035B` branch — levels `[100 RESTING, 110 EMPTY, 120 EMPTY, 130 RESTING, 140 RESTING]`, state RUNNING, zero new requests.

## Symptom
The level at 110 is EMPTY for the rest of the run. The Orders panel shows three resting orders of a four-order ladder, and the bot says RUNNING.

## Root cause
`GridReconciler._apply_missed_fills` (`src/modules/bots/application/services/grid_reconciler.py`, the loop over `runtime.open_orders`) ended every saved order that was missing from the exchange with `drop_order(...)` after applying what it executed. `drop_order` empties the level (`LevelEvent.ENDED`) and returns no action, whereas `on_end` empties it **and** re-places the order once for what it still owes (or halts `LEVEL_KEEPS_ENDING`). The restart path never mattered much (the owner is present); a periodic reconcile on an unattended bot made the hole permanent.

## Fix
`_apply_missed_fills` is split into `_catch_up` (the executed quantity beyond what the bot counted, applied as a fill) and `_end_missing` (a missing order the level still holds runs `on_end` with the `LadderRules` of the symbol, `hold=True`, so the re-placement is held like a counter order and released by the caller when the bot is RUNNING; a halt becomes a `ReconcileMismatch`, which the gap reconcile confirms with a second run). Both entry points (`run`, `compare_with_exchange`) share it. A saved order the history does not hold counts as having executed nothing: open orders are read before the history, so an order that fills later is still listed open.

## Regression test
`tests/unit/modules/bots/application/services/test_grid_reconciler_gap_unfilled.py`: `test_an_order_cancelled_in_the_gap_is_laid_again`, `test_a_paused_bot_holds_the_laying_again_of_a_cancelled_order`, `test_an_order_cancelled_twice_within_a_minute_halts_the_bot` (red before: no request was placed, the level stayed EMPTY; the second cancel found no order to cancel), and `test_a_cancel_found_by_two_reconciles_is_laid_once` (idempotence).

## Verification
Red before on `be67b47` (three tests above failed by assertion), green after; the bots unit tier (1,318 tests) and the commit tier pass. Positive proof the mechanism ran: the simulated book's request list shows the BUY at 110 placed once, and the reconcile logs `reconcile … missing from the exchange, ended without filling`.
