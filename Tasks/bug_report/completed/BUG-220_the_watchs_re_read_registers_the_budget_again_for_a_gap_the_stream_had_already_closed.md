# BUG-220 — A divergence the stream had already closed was still confirmed by registering the budget again, and a position the pause kept from being read stayed unknown until the next update

- **Reported:** 2026-10-15 (the second part of `BUG-216`, owner's Futures testnet log, Long Grid `djwx0w`; the reviewer of PR #528 noted the deferred-read gap as N2)
- **Severity:** 🟡 P2. Cost, not loss: each re-read after a transient ordering gap spent ~20 of the minute's request weight, in the minute the exchange was already limiting the IP, and a pause left the session's belief about an open or closed position stale until the next `ACCOUNT_UPDATE`.
- **Status:** ✅ Fixed (2026-10-15)
- **Board:** The watch confirmed a divergence by registering the budget again (positionRisk twice, the fills' history, the open orders) even when the order's report had landed and the book agreed with the stream's last figure; and a re-read the pause deferred left `known_open_symbols` and the desk's "closed" event waiting for the next update. Fix: the book answers from the figure the stream last reported (`agrees_with_last_report`), the recheck reads nothing when it agrees, and the stream settles from the payload's amount what the amount alone carries.
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) → `bots` (`application/services/risk/`, `kinds/grid/watch/`) and `trading` (`application/owner_*book*.py`, `adapters/binance/futures_user_data_stream.py`)
- **Environment:** Futures HTTP fake exchange at `5ac84b36` (`master-warrior`), with the request-weight meter of `BUG-216`. Not run on a live exchange.

## Reproduction
1. Futures Long Grid running on the fake exchange; the price crosses an entry level.
2. The account's report (`ACCOUNT_UPDATE`, `pa` = the new amount) is delivered before the order's (`ORDER_TRADE_UPDATE`): the book differs from the figure for the seconds between them, and trading reports `POSITION_CHANGED_UNORDERED`.
3. After `position_recheck_delay` (5 s) the watch re-reads. Count the requests the fake received.

Expected: nothing, the fill has landed. Actual before the fix: one registration (`userTrades` among its reads, ~20 weight); after a 12-fill burst the same single registration, once.

## Symptom
The owner's log, 19:34, shows the divergence line and then the re-read as the pause began; the fake reproduces the extra reads, not the owner's figure. Separately, with the exchange's pause running, the position re-read of an `ACCOUNT_UPDATE` is refused and waits (`DeferredRereads`, `BUG-216`); until the next update `known_open_symbols` held the old belief and a position that closed was never told closed.

## Root cause
1. **The confirmation had no cheap answer.** `PositionRechecks.recheck` (`risk_reads_futures.py:76`) always registered the budget again (`GridHousekeeping.register`, several weighted reads) to find out whether the divergence persisted. Trading already holds the answer for the commonest case in memory: `OwnerPositionBook` keeps the figure the stream last reported (`_last_exchange`, set by `cross_check` from each `ACCOUNT_UPDATE`'s own `pa`), and the book has applied the fill by the time the delay has passed. No port exposed the comparison.
2. **The pause deferred more than the pause forced.** `FuturesUserDataStream._handle_account_update` read every changed symbol's position by REST to learn two facts the payload already carries (whether the symbol holds a position, and that it closed); the refusal deferred both with the rest.

## Fix
- `IOwnerBook.agrees_with_last_report()` (Spot book: `False`; `OwnerPositionBook`: the last reported figure within one step of the derived position; a pure query that consumes no divergence), `OwnerBooks.agrees_with_last_report(tag, owner_id)`, and `ITradingSession.owner_position_agrees_with_the_stream(owner_id, tag)` (local, no round trip; `False` means "not known to agree", never "known to differ").
- `PositionRechecks.recheck`: asks that first; if the book has caught up it returns "agrees" and reads nothing. Otherwise it registers as before, so the exchange alone decides whether a divergence persists, and the second-look rule of `BUG-218` and the halt are unchanged.
- `position_reading_effects.py`: `apply_positions` (moved out of the stream, unchanged) and `settle_from_amount`, which the stream calls when the pause refuses a read: `known_open_symbols` and the "closed" event come from the payload's amount; the mark, leverage and liquidation price of an open position still wait for the deferred read. The stream's re-read loop became `_reread_positions` (complexity).

## Regression test
- `tests/integration/modules/bots/test_the_streams_ordering_gap_costs_the_exchange_nothing_on_the_fake_exchange.py`: fill first / account first (red on the old tree for account first: one registration), a fill reported twice (red: one registration), a lost order report (one registration, the exchange's record settles it), a trade by hand (registered, then `POSITION_MISMATCH` halt), and a burst of 12 fills with the account first (red: one registration; weight inside the per-fill budget).
- `tests/unit/modules/bots/application/services/test_a_recheck_reads_nothing_when_the_book_has_caught_up_with_the_stream.py`: agrees → no registration; not agreeing → one; a divergence the exchange confirms still halts.
- `tests/unit/modules/trading/application/test_a_book_says_whether_it_holds_what_the_exchange_last_reported.py`: no report, report before the fill, fill before the report, one step vs two, the query changes nothing, Spot, the registry's owner check.
- `tests/unit/modules/trading/adapters/binance/test_the_report_settles_what_a_pause_kept_the_stream_from_reading.py`: opened and closed during a pause settle from the report (red on the old tree); a deferred symbol this payload does not name is not guessed.

## Verification
Regression tests red on the original `src/` and green after. Commit tier and the pull request's `-Full` run: see the pull request. Positive proof the new mechanism ran: the burst's request log holds no `userTrades` after the delay (one before), and the lost-report test holds exactly one.

Unverified: anything on the real Futures Testnet, and whether the testnet's `ACCOUNT_UPDATE` carries the amount at the event as the fake's does (the premise of `EPIC-039D`'s cross-check, `EPIC-039L`).

The price of the in-memory answer (review of PR #533): a foreign trade that lands after the last `ACCOUNT_UPDATE` can heal wrongly for about one recheck delay. Example: a foreign trade, then a bot fill of the same size, with the recheck falling between the bot fill and its `ACCOUNT_UPDATE`: the book matches a figure the exchange has already moved past. The next `ACCOUNT_UPDATE` carries a new cause, `cross_check` reports it, the watch re-arms, and its recheck sees the disagreement, registers and halts. Before this change the REST read would have caught it at once. Accepted: it needs a foreign trade and a bot fill of the same size inside one report gap, it is bounded by one delay, and it can only delay a halt, never lose one. The pause-branch settlement stops at the generation fence (`BUG-094`) before it defers or writes anything.

Not done, by design: a position that is open when the pause refuses its read keeps its event (mark, leverage, liquidation price) waiting for the next update. Building it from the payload would invent three fields. The desk's headline for an order the pause refused is `BOT-181`.
