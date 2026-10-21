# BUG-256 — The exchange's pause (429, 418) on a later opening slice left the position without a stop and resumed a smaller grid

- **Reported:** 2026-10-21 (the reviewer of the `BUG-254` pull request, round 3, as a pre-existing finding; filed at the coordinator's request)
- **Severity:** 🔴 P1 — real money: a leveraged position half opened, no protective stop for the whole pause (nothing can be sent during it, a stop included), then a grid one upper level short of the plan the owner saw
- **Status:** ✅ Fixed (2026-10-21)
- **Board:** A 429 or 418 on the opening's second slice or later put the bot in AWAITING_RECOVERY with half the opening and no stop; the resume re-derived the ladder from the position held and ran a smaller grid. Fixed with `BUG-254`'s rule extended to the exchange's pause: `opening_outcome` makes any pause after a filled slice a refused start, so the start closes (the close waits for the pause's end like any stop).
- **Context:** Start a Futures or Spot Grid (`Docs/SPEC/`) → bots (`src/modules/bots/`) → `application/services/` (`orders/order_outcome.py`, `positions/opening_futures.py`, `positions/opening_spot.py`)
- **Environment:** `master-warrior` 8b00d52b (after `BUG-254`). Not seen in the owner's runs: found by reading and reproduced on the Futures fake.

## Reproduction
`tests/integration/modules/bots/test_an_exchange_pause_in_the_openings_later_slice_closes_the_start_on_the_fake_exchange.py`: the fake answers the connection check of the order after the first with a 429 and `Retry-After` 30 (as `BUG-216`'s journey does). Before the fix the bot ends AWAITING_RECOVERY, `rate_limited`, "any position stays open ... no protective stop stands over it; resumes by itself", position 0.006 of 0.012. With the user stream delivering the resume ends RUNNING with 0.006 and a ladder one upper level short (the `BUG-254` probe). Frequency: every time the pause lands on a later opening slice.

## Symptom
```
STARTING -> AWAITING_RECOVERY on halt_transient (rate_limited: opening slice 2: ... this bot cannot close it until trading is back; no protective stop stands over it; resumes by itself when the pause ends)
```
Expected: the same rule as for the app's own pause (`BUG-254` D3): the start closes, or the opening is finished.

## Root cause
Read at `master-warrior` 8b00d52b. `PositionOpening._open_position` and `SpotOpening._buy_opening` send the opening in slices and hand a slice that is not done to `fail_with`. A `RATE_LIMITED` outcome there is `pause_with` → `state.halt(RATE_LIMITED)` → AWAITING_RECOVERY (`grid_order_failure.py` `fail_with`, `pause_with`), the right answer for a ladder order. After a slice filled it is not: the position is open, the stop (`GridStartSequence.run`, step 1a) is placed only after the whole opening is counted, and nothing can be sent during the pause; and the resume re-derives the ladder from the position held (the recovery's propose-and-confirm), it does not finish the opening. `BUG-254`'s `opening_outcome` handled only the app's own pause (it keyed on `OrderOutcome.own_budget`), so the exchange's pause, the same outcome kind through the same step, kept the old behaviour.

## Fix
- `order_outcome.py` `opening_outcome`: keyed on the outcome kind, not on who asked. A `RATE_LIMITED` outcome at slice > 1 is `REFUSED`, so the start is refused and closes. `OrderOutcome.own_budget` (added by `BUG-254` only for this) is removed: it had no other reader.
- Consistent with `BUG-254`'s decision D3, whose text now names the exchange's pause. During the exchange's pause the close cannot go and the position is bare until it ends; that cannot be removed (the gate refuses every request, a stop included), and the close then runs on the stop's own retry. Not done, by decision: placing the stop between the opening's slices (it would shrink every later bare window, at the cost of one more request round and a change to the start order); a candidate for the owner.

## Regression test
- `test_an_exchange_pause_in_the_openings_later_slice_closes_the_start_on_the_fake_exchange.py::test_the_exchanges_pause_on_the_openings_second_slice_closes_the_start` — failed before the fix with AWAITING_RECOVERY; passes after (STOPPING while the pause runs, the position still held, then STOPPED and flat once the pause ends and the stop is asked again). Real executor, handler and gate; the 429 comes through the connection check.
- `test_bot_order_gateway_own_pacing.py::test_a_pause_after_an_opening_slice_filled_is_a_refusal` (own budget and exchange, slices 1 and 2) replaces `test_an_exchange_pause_is_a_pause_in_every_opening_slice`, which pinned the old behaviour on purpose; stronger coverage of the same path.

## Verification
Regression test red on 8b00d52b (and red again with `opening_outcome` made a no-op), green after; commit tier and the suites in the pull request.

## Suggested next steps
None open. Candidate for the owner: a protective stop between the opening's slices.
