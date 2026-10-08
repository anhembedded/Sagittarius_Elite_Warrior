# BUG-188 — A partial fill of a still-open order, missed in a stream gap, halts the bot instead of being counted

- **Reported:** 2026-10-08 (found by the `EPIC-035B` session designing the gap reconcile; not reported by a user)
- **Severity:** 🟡 P2 — safe but noisy: the bot halts with `INVENTORY_MISMATCH` and takes its ladder off, so the owner must resume. No wrong order is placed.
- **Status:** Open
- **Board:** After a stream gap, an order that partly filled and is still resting is not re-read: the bot's inventory stays short of the exchange's, the reconcile's inventory check fails twice, and the bot halts.
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
Not yet fixed. `_apply_missed_fills` reads an order's history record only when the order is missing from the open orders; the executed quantity of an order that is still open is never compared with the level's `executed`. `EPIC-035Q` (the reconciler reads the executed quantity of an *adopted* order, depends on `EPIC-035B`) is the same read for the other case.

## Fix
Not fixed. Candidate: for every saved order, read its executed quantity (open orders carry it, or the record does) and apply the difference as a fill; do it with `EPIC-035Q`.

## Regression test
Not written. Planned: `test_a_partial_fill_missed_in_the_gap_is_counted_and_the_order_stays_resting`, red before.

## Verification
Not run.

## Suggested next steps
Fold into `EPIC-035Q` (same read), and keep this report as its failing case.
