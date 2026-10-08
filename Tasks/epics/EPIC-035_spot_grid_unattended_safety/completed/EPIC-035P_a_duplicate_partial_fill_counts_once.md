# EPIC-035P — A duplicate partial fill counts once

**Status:** ✅ Done (2026-10-08)
**Source:** the owner's Spot Grid audit, 2026-10-08, finding L1 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 4 of [EPIC-035](../README.md).
**Risk:** 🟡 — double counting inflates inventory and then halts the bot
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** None

---

## 1. Context and problem
Audit L1: `BotOrderFill` carries no trade id, so a duplicated partial-fill event is counted twice; the trading budget then refuses the oversized SELL and the bot HALTs. Cited: `src/modules/bots/contracts/bot_order_events.py:17-25`, `src/modules/trading/adapters/binance/venue_event_emitter.py:79-90`. Verify.

**Re-verified on `3064fe0` (master-warrior), 2026-10-08.**
- `BotOrderFill` carried no trade id (`bot_order_events.py:17-25`). ✅ holds.
- `venue_event_emitter.py:79-90` is **partly stale**: `order_filled` already took a `trade_id` (EPIC-029A, for the owner books) and the Spot parser already read it (`fill_trade_id`, `spot_user_data_event_parser.py:137`); `OrderFilledEvent` simply dropped it before the bots' router saw it. Futures reports no trade id (`futures_order_updates.py:105`), so the field is optional.
- Reproduced through the real path (emitter → bus → `BotEventRouter` → executor): one report delivered twice moved the inventory by 0.006 instead of 0.003. **Not exercised:** the audit's last step (the oversized counter SELL refused and the bot halted) is inferred from the doubled inventory, not run.
- `EPIC-035B`'s gap reconcile adds a second source of the same fill (history), which is why the reconciler is in scope.

## 2. Acceptance criteria
- [x] The fill event carries the exchange trade id. `OrderFilledEvent.trade_id` and `BotOrderFill.trade_id`, both `int | None`; the emitter and the router pass it. Evidence: `test_venue_event_emitter_trade_id.py` (red before: no such attribute).
- [x] The executor ignores a fill whose (order id, trade id) it has already applied. `AppliedFills` in the run context, checked first in `GridFacts._apply_fill`. Evidence: `test_a_duplicated_partial_fill_is_counted_once`, `test_a_duplicate_stream_event_reaches_the_bot_once_through_the_real_path` (red before: 0.006), and the boundaries `test_two_different_trades_of_one_order_both_count`, `test_a_fill_without_a_trade_id_is_never_taken_for_a_duplicate`, `test_the_same_trade_id_on_another_order_is_another_fill`.
- [x] The reconciler's replay uses the same key. `GridReconciler._catch_up` records the trade ids of every fill it applies from history. Evidence: `test_a_fill_the_reconciler_replayed_is_not_counted_again_by_the_stream` (red before: counted twice).

## 3. Design
Idempotent consumer on a natural key.

Chosen: the pair (client order id, trade id), in a bounded per-run memory (`AppliedFills`, 4096 fills, oldest forgotten first) beside `OffLadderOrders` in the run context. A fill with no trade id is never taken for a duplicate: nothing is guessed from its quantity. The ledger is not persisted: a restart reads what the exchange holds (`GridReconciler`), and a duplicate arrives within seconds of its original. Price knowingly paid: a reconcile that records trades and is then not applied (a first-strike disagreement, a halt) leaves those ids in the ledger; the confirming run re-applies the same quantity from history, so no fill is lost, and a halted bot takes no fills anyway.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/events/order_filled_event.py` | `trade_id` |
| `src/modules/trading/adapters/binance/venue_event_emitter.py` | Puts it on the event |
| `src/modules/bots/contracts/bot_order_events.py` | `BotOrderFill.trade_id` |
| `src/modules/bots/application/event_handlers/bot_event_router.py` | Passes it on |
| `src/modules/bots/application/services/applied_fills.py` | New: the bounded ledger |
| `src/modules/bots/application/services/grid_run_context.py` | Holds the ledger |
| `src/modules/bots/application/services/grid_facts.py` | Ignores a known fill |
| `src/modules/bots/application/services/grid_reconciler.py` | Records the trades it replays |

## 5. Testing
Unit tier, the real executor over the simulated venue: `test_grid_duplicate_fill.py` (6), `test_applied_fills.py` (4, the bound), `test_venue_event_emitter_trade_id.py` (2). Red before: all 8 behavioural tests failed. Mutations (the ledger never recording replayed trades; `knows` always false; a key without the order id) each turned the file red. Green after: `tests/unit/modules/bots`, `tests/unit/modules/trading` and `tests/unit/architecture`.

## Implementation notes
- SPEC-014 §Out-of-scope no longer says a duplicate is counted twice, and its test table has the row.

## Resume
Done. Nothing owed.
