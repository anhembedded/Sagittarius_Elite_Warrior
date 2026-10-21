# BUG-258 — Every Futures start logs a WARNING "gap reconcile disagrees (position_mismatch: saved 0 against 0.19)"

- **Reported:** 2026-10-21 (the owner's desktop log, futures_mainnet, bot `xvp0x7`, 21:33 +07, via the coordinator session)
- **Severity:** 🟡 P2 — the bot self-heals, but the run-log scan treats the WARNING as a finding, and a different timing could act on a mismatch that is not real
- **Status:** ✅ Fixed (2026-10-21)
- **Board:** The opening counted from the exchange reached the runtime only through the user-data stream's fill report, so the first gap reconcile saw a saved position of 0; fixed by booking the opening's trades from the order history right after the count, with their trade ids remembered so the stream's report counts once.
- **Context:** SPEC run a grid bot → `src/modules/bots/` → `application/kinds/grid/start/`, `application/kinds/grid/recovery/`
- **Environment:** master-warrior at `68e1227`, Futures mainnet BNBUSDT, opening 0.19 at 746.14. Not reproduced on a real exchange; reproduced at the unit tier.

## Reproduction
1. Start a Futures Grid whose opening is a market order, with the user-data stream reporting the fill later than the start's end (late, or down).
2. The first `GridStreamGap.reconcile` runs right after `STARTING -> RUNNING`.

Expected: no disagreement. Actual: `saved 0 against 0.19 derived from the exchange`.

## Symptom
```
21:33:15,244 STARTING -> RUNNING on ladder_ready
21:33:16,797 Owner budget registered ... position 0.19, 31 open order(s).
21:33:16,798 WARNING Bot xvp0x7: gap reconcile disagrees (position_mismatch: saved 0 against 0.19 derived from the exchange); confirming with a second run
21:33:16,824 the exchange's position 0.19 differs from the bot's 0 (position_changed_unordered); re-reading in 5 s before acting
21:33:23,013 the position agrees again after the re-read; left running
```

## Root cause
At `68e1227`, `PositionOpening._count_opening` (`opening_futures.py:131`) counts the opening from the exchange through trading's registration, but writes nothing to the bot's runtime. The runtime books a market order's fill only in `GridFacts._apply_fill` (`grid_facts.py:256`, `book_market_fill`), on the stream's report. `PositionExposureCheck.check` (`exposure_check_futures.py:81`) compares that runtime with the position trading derives from the exchange's history. Whenever the stream's fill lags the first reconcile, the two differ. `GridMissedFills.apply` (`grid_missed_fills.py:99`) replays only the ladder's saved orders, so the reconcile cannot recover a market order. The same holds on Spot (`SpotOpening`; BUG-194 fixed trading's book, not the bot's runtime).

The gate was green because the simulated venue of `grid_world` never reports a market order's fill, and `gap_world.running()` hides it by deriving the inventory the runtime holds (`derive(str(world.runtime().inventory))`), so no test ever compared a started runtime with the exchange.

## Fix
- `start/opening_fills_booking.py` → `OpeningFillsBooking.book`: after the opening is counted and before the stop and the ladder, read each opening slice's record and trades from the order history, book them with `book_market_fill` and remember `(client order id, trade id)` in `AppliedFills`, so the stream's report of the same trade, early or late, is ignored as a duplicate. A history that does not answer is a WARNING `[opening-fills]` and leaves the slice to the stream, as before.
- `OffLadderOrders.add_opening` / `openings`: both opening strategies name their slices, so the booking reads no private state.
- Design: `Docs/MODULES/bots/06-runtime.md` start paragraph.

## Regression test
`tests/unit/modules/bots/application/services/test_a_start_books_the_opening_it_counted.py` — three tests over the position world with the venue's history showing the filled market order and the stream silent: the saved inventory holds the opening at RUNNING; a gap reconcile right after the start logs nothing at WARNING; a late stream report of the same trade does not count it twice. All three failed before (inventory 0; the inline confirm run halted the bot), green after.

## Verification
Commit tier green (`ci-local.ps1 -SkipTests`), architecture guards, `tests/unit/modules/bots`, `tests/unit/modules/trading` (8534) and `tests/integration/modules/bots` (422) green locally. Positive proof the mechanism ran: the INFO line `opening fill <trade> of <order> booked from the exchange's record [opening-fills]`. Not run on a real exchange.
