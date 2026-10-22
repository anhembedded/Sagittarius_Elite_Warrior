# BUG-264 — A filled order leaves no INFO line in the journal, so a Cycles figure cannot be audited

- **Reported:** 2026-10-21 (the owner's VPS journal for bot `6tszoz`, relayed by coordinator session `session_016sGQHsRy729Fp4cY1cTXfu`)
- **Severity:** 🟢 P3 — the books were not shown wrong; the evidence to check them was missing
- **Status:** ✅ Fixed (2026-10-21)
- **Board:** The owner's Cycles figure for `6tszoz` read one short of the paired SELL fills the journal implied, and the journal held no line for a fill (only a position divergence and the counter order); each whole fill now logs its level, side, price, cycles and grid profit, and whether it closed a cycle.
- **Context:** Run a grid bot → bots (`src/modules/bots/`) → `application/kinds/grid/grid_fill_announcer.py`
- **Environment:** Owner's VPS host, Futures Testnet, bot `6tszoz` (LONG x5, 48 geometric grids 2345-2816), 2026-10-21; the build before `b4127dfa`.

## Reproduction
The journal 16:50-21:10 (+07) holds, for each fill, `the exchange's position X differs from the bot's Y (position_changed_unordered)` and, about 0.5-1.3 s later, the counter order; no line says a fill was booked. `bot list` read Cycles 18 / Grid profit 1.64 at about 16:55, 19 / 1.73 at about 21:05, 20 / 1.83 at 23:40. By the code's rule (a SELL that carries `paired_buy_price` closes a cycle, `grid_reactions._counter`, `grid_books.book_cycle`) the journal's counter placements imply three closing SELLs after 16:55 (L13 at 18:24, L14 at 20:52, L15 at 21:48): 21 expected, 20 shown.

## Symptom
One cycle of 0.09 USDT is missing from Cycles and Grid profit, and nobody can say which fill it was.

## Root cause
Not established for the missing cycle. Established: (a) the fill announcer logged a whole fill only at DEBUG (`grid_fill_announcer.py`, `announce`, read at `4cb6d47a3`), so an INFO journal could not tell a booked fill from a missed one, and the line carried no order id to match against the exchange's trade history; (b) Total PnL (`realised_total + unrealised + funding`, `grid_pnl.py`) agrees with trading's owner book within 0.0002 (realized_pnl 1.3455, fees 0.6327, funding -0.0902, unrealised 18.857 at the mark), which rules out a lost **fill** but not a lost **pairing**: grid profit is not part of Total PnL, and every sell, cycle sells included, books into `realised_total` (`grid_books.book_inventory`), so a SELL booked as inventory but not as a cycle leaves Total PnL unchanged. "Unrealised" is `inventory x (mark - average cost)` (`grid_pnl._unrealised`).
Replayed and ruled out: a saved paired SELL keeps its pairing across the codec and a stop/restore/resume (simulated world). Found by review round 1 and tracked as `BUG-265`: an order the reconcile **adopts** (`grid_reconciler._level_order`) carries no `paired_buy_price` and `grid_reactions.adopted` drops the held order that held it, so its fill closes no cycle. The owner's journal for 16:50-21:10 holds no `adopted` line, so that path did not run on `6tszoz` in that window; which of the L13 SELL at 18:24 and the L14 SELL at 20:52 the count lost is still open, and the exchange's trade history for the tag decides it (the recount: 18 at 16:55, +L13 +L14 = 20 expected at 21:05 against 19 shown; +L15 at 21:48 = 21 against 20 at 23:40; the 21:48 line is from the owner's later journal, which the coordinator sent after the 21:10 cut).

## Fix
`GridFillAnnouncer.announce` logs each whole fill at INFO: `Bot <id>: <order id> L<n> <side> <qty> @ <price> filled whole; <cycles> cycle(s), grid profit <p> (this fill closed a cycle: +<x> | closed no cycle) [order-filled]`. One line per order that filled whole, the same rate as the existing placement lines, never per trade. A fill missing from the journal now means it was not booked.

## Regression test
`tests/unit/modules/bots/application/services/test_a_filled_order_leaves_a_line_in_the_journal.py`: an entry fill says it closed no cycle; the completing fill says the cycle and its profit. Red before: no INFO line is logged.

## Verification
The new test and the bots unit tier locally; the full gate is GitHub Actions'. Not verified: that the missing cycle recurs; the next occurrence will show the fill that was not booked.
