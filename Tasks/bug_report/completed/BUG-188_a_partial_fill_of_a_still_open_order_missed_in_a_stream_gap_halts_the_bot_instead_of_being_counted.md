# BUG-188 — A partial fill of a still-open order, missed in a stream gap, halts the bot instead of being counted

- **Reported:** 2026-10-08 (found by the `EPIC-035B` session designing the gap reconcile; not reported by a user)
- **Severity:** 🟡 P2 — safe but noisy: the bot halts with `INVENTORY_MISMATCH` and takes its ladder off, so the owner must resume. No wrong order is placed.
- **Status:** ✅ Fixed (2026-10-08)
- **Board:** After a stream gap, an order that partly filled and was still resting was not re-read: the bot's inventory stayed short of the exchange's, the reconcile's inventory check failed twice, and the bot halted. Cause: `_apply_missed_fills` read history only for orders missing from the open orders. Fix: every saved order is read (one pass over history) and what it executed beyond what the bot counted is applied as a fill, resting or not.
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) → bots (`src/modules/bots/`) → `application/services/grid_reconciler.py`
- **Environment:** Linux container; `master-warrior` `546b8a3` with the `EPIC-035B` branch; read from the code and from the reconcile's own tests; not run on an exchange.

## Reproduction
1. A RUNNING Grid with a BUY resting at 110.
2. 0.003 BTC of it fills (a partial fill larger than the symbol's step) while the user-data stream is down. The order stays open.
3. The stream reconnects and `reconcile_after_gap()` runs, twice (a disagreement is confirmed by a second run before it halts).

Expected: the executed quantity is applied to the level (its counter order owed only once the order is whole), and the bot stays RUNNING.
Actual (established by reading, not run): `GridReconciler._apply_missed_fills` skips a saved order that is still open (`saved.client_order_id in open_ids → continue`), so the 0.003 BTC is never applied; the derived inventory exceeds the saved one by more than a step; both runs find `INVENTORY_MISMATCH` and the bot halts.

## Symptom
HALTED, reason `inventory_mismatch: saved … against … derived from the exchange`, ladder cancelled.

## Root cause
`GridReconciler._apply_missed_fills` read an order's history record only when the order was missing from the open orders (`saved.client_order_id in open_ids → continue`); the executed quantity of an order that is still open was never compared with the level's `executed`. An open `Order` carries no executed quantity, so the read has to come from history.

## Fix
`_catch_up` (see `BUG-187`) runs for every saved order, resting or not. History is read once per reconcile through the new `BotOrderGateway.order_records(ids, since)` (a single paged pass; one `order_record` read per order would multiply the rate-limit weight by the ladder's size). The difference is applied through `on_fill` with `hold=True`, so the counter order is owed only once the order is whole, and the fee comes from the order's trades less what the bot already counted, as for a closed order.

## Regression test
`tests/unit/modules/bots/application/services/test_grid_reconciler_gap_unfilled.py`: `test_a_partial_fill_missed_in_the_gap_is_counted_and_the_order_stays_resting` and `test_the_fee_a_missed_partial_fill_paid_is_counted_once` (red before: HALTED, `INVENTORY_MISMATCH`), `test_a_partial_fill_is_applied_once_however_often_the_reconcile_runs` (idempotence).

## Verification
Red before on `be67b47`, green after; the bots unit tier and the commit tier pass.

## Not covered (by name)
- A stream fill event for the same partial fill that is already queued behind the reconcile is counted a second time: `BotOrderFill` carries no trade id. That is `EPIC-035P` (a duplicate partial fill counts once), which also owns the reconciler's replay key.
- An *adopted* order (one the saved ladder did not know) still starts at `executed = 0`: that is `EPIC-035Q`, which stays open; this fix delivers its read for saved orders only.
