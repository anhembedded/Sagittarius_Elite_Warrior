# BUG-185 — A reconcile empties the level of an order that ended without filling and never re-lays it

- **Reported:** 2026-10-08 (found by the `EPIC-035B` session while writing the gap reconcile; not reported by a user)
- **Severity:** 🟡 P2 — a hole in a running grid: one level stays empty until the bot is stopped and started again, so the grid earns nothing there. No money is at risk and no order is wrongly placed.
- **Status:** Open
- **Board:** A reconcile (after a restart, and since `EPIC-035B` after every stream reconnect) drops a saved order that is no longer open and executed nothing; its level stays empty and nothing re-lays it, where the stream's own end event would have re-placed it once.
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
Not yet fixed. Established by reading and by the scratch run above: `GridReconciler._apply_missed_fills` (`grid_reconciler.py`, the loop over `runtime.open_orders`) ends every saved order that is missing from the exchange with `drop_order(...)` after applying what it executed. `drop_order` empties the level (`LevelEvent.ENDED`) and returns no action, whereas `on_end` empties it **and** re-places the order once (or halts `LEVEL_KEEPS_ENDING`). The restart path never mattered much (a restarted bot is reconciled once and the owner is present); a periodic reconcile on an unattended bot makes the hole permanent.

## Fix
Not fixed. Candidate: for a saved order missing from the exchange and not fully filled, run `on_end` (with the same `LevelEnd` the stream builds) instead of `drop_order`, in both entry points, and place what it returns. `EPIC-035C` (stuck states and unmanaged orders) touches the same file; decide there or in its own task.

## Regression test
Not written. Planned: `tests/unit/modules/bots/application/services/test_grid_reconciler_gap.py::test_an_order_cancelled_in_the_gap_is_laid_again`, red before.

## Verification
Not run.

## Suggested next steps
Schedule with Phase 1's `EPIC-035C` or as its own task; the change is local to `_apply_missed_fills`.
