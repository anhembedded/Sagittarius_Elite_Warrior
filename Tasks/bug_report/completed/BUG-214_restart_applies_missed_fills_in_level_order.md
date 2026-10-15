# BUG-214 — A Grid bot restarted after two rungs filled while the app was closed halts with `DUPLICATE_LEVEL_ORDER` (and a Futures bot closes its healthy position)

- **Reported:** 2026-10-15 (independent review of PR #523, finding 2; probed on Futures Long and Neutral)
- **Severity:** 🟡 P2. Money-safe (the bot ends flat with no orders) but a healthy Grid is stopped by a restart, and a Futures bot realises a loss closing at market when nothing was wrong.
- **Status:** ✅ Fixed (2026-10-15)
- **Board:** A restart after two or more rungs filled while the app was closed halted the bot with `DUPLICATE_LEVEL_ORDER`. Cause: the reconcile applied the missed fills in level order, not the order the exchange filled them, so a counter was computed before the fill that vacates its level. Fix: `GridMissedFills.apply` orders the fills by their newest trade's time (trade id on a tie).
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), restart of a Grid → `bots` → `application/kinds/grid/recovery/` (`GridMissedFills`, called by `GridReconciler`)
- **Environment:** Spot and Futures testnet fakes at `a1a875e` (master-warrior). Not run on a live exchange.

## Reproduction
1. Start a Grid; stop the app.
2. While closed, the price falls through two BUY rungs one after the other (Futures Long: 63,000 then 62,000; Spot: the two highest BUYs, higher first).
3. Start the app and Resume.

Expected: both fills are applied, the bot is RUNNING with the counters laid. Actual: HALTED `duplicate_level_order`; Futures then closes the position at market.

## Symptom
```text
Bot 1vl0p5: RECOVERING -> HALTED on reconcile_mismatch (duplicate_level_order: L1 already holds an order; the counter of L0 cannot go there) [bot-transition]
Bot hghyre: HALTED -> STOPPING on stop (duplicate_level_order: ...; any position is closed at market, as a leveraged position is never left bare)
```

## Root cause
`GridMissedFills.apply` (`grid_missed_fills.py`, before the fix, the `for saved in runtime.open_orders` loop) walked the saved orders in level order and applied each one's missed fill at once. A fill's counter goes to the neighbouring level, which is free only after the fill that held it is applied. When the exchange filled the higher rung first (price falling), the lower rung's counter met the higher rung's still-unapplied BUY: `on_fill` returned `Halt(DUPLICATE_LEVEL_ORDER)`. The order the fills happened in was available all along: every `TradeRecord` carries `time` and a rising `trade_id`, and the loop already fetched the trades of each order. Spot and Futures share this code, so both are affected (Long reproduced by the reviewer; Short and Neutral reach it the same way, in both directions).

## Fix
`grid_missed_fills.py`: `apply` first collects each saved order's missed fill with its trades (`MissedFill`), then applies them sorted by `event_order` (newest trade's time, trade id on a tie; a fill history does not date goes last, in level order), then ends the saved orders missing from the exchange as before. `catch_up` (used for adopted orders) shares `_apply_missed`. The duplicate guard in `on_fill` is untouched: a genuine duplicate still halts.

Not a call-site patch: the order of replay is now decided in the one place that replays history, for every kind and venue. Not touched: `grid_reconciler.py` (changed by #521/#523), the stream path (it applies fills in delivery order already).

## Regression test
- `tests/integration/modules/bots/test_a_restart_applies_missed_fills_in_the_order_they_happened_on_the_fake_exchange.py`: the real reconciler against the fake exchange, Futures Long and Spot, two BUYs filled while closed in the order opposite to level order. Red before the fix with `duplicate_level_order` (both); green after.
- `tests/unit/modules/bots/application/kinds/grid/recovery/test_missed_fills_are_ordered_by_the_exchange.py`: the sort key (order by newest trade, trade-id tie-break, undated last).
- Not covered: a counter that fills after its parent. A counter is laid only while the app runs, so with the app closed it never exists on the exchange; the one case where it can (an adopted order, `EPIC-035Q`) is applied after the saved ones, i.e. after its parent, which the existing adoption tests exercise.

## Verification
Regression tests red before, green after; positive proof is the `[missed-fill]` log lines in the green run, in trade order. Commit tier: see the pull request.
