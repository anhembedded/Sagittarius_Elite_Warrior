# BUG-233 — A healthy `CLOSE_AT_MARKET` stop of a Futures bot writes `WARNING Position state mismatch ... app believed open, exchange reports flat`

- **Reported:** 2026-10-19 (the reviewer of #580, by a probe on the Futures fake at `7e0afce`, and again at `159fbfd`)
- **Severity:** 🟢 P3. The stop is correct; the WARNING cries wolf at the end of every healthy stop, and the run-log scan treats WARNING as a failure.
- **Status:** Open
- **Board:** A Futures bot stopped with a close ends flat and STOPPED, then `LiveTradingCoordinator` warns that the app "believed open, exchange reports flat": the mirror of BUG-203, because the owner's book is cleared at `STOP_CONFIRMED` before the exchange's flat report arrives.
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), stopping a Futures Grid → `trading` (`src/modules/trading/application/position_state_reconciler.py`, `OwnerBooks`) and `bots` (`grid_stop_sequence.py`)
- **Environment:** the Futures fake (`booted_futures_bots`) at `159fbfd` and `c5f00e2`; not seen on a live exchange (a testnet journal would show the same line).

## Reproduction
1. Start a LONG Futures Grid on the Futures fake.
2. Stop it with `CLOSE_AT_MARKET`.
3. Read the `App.LiveTradingCoordinator` records.

Expected: no WARNING; the bot closed its own position. Actual: one WARNING per healthy stop.

## Symptom
```text
App.LiveTradingCoordinator: Position state mismatch for BTCUSDT: app believed open, exchange reports flat — exchange wins.
```
Reproduced by the reviewer at `159fbfd` (before #580) and at `7e0afce`, so #580 neither caused nor fixed it.

## Root cause
Not yet shown by a fix. From reading at `c5f00e2`: a budgeted owner's orders never mark the symbol open, so the session learns the owner's position from the exchange's first report and then holds `known_open_symbols` (`position_state_reconciler.py` → `reconcile_position_state`; the opening case is #580). The stop's close empties the position, `grid_stop_sequence.py` → `_confirm` clears the owner book at `STOP_CONFIRMED`, and the account's flat report arrives after that. `OwnerBooks.has_owner_on` is then false, so the correction `open → flat` is not recognised as the owner's own and warns. The same "a belief nobody held" family as BUG-203, on the way out.

## Fix
Not started.

## Regression test
Not written. Candidate: `tests/integration/modules/bots/` on the Futures fake, a `CLOSE_AT_MARKET` stop with a handler on `App.*` for WARNING, expecting none.

## Verification
Not run.

## Suggested next steps
Decide where the knowledge lives: either the book outlives the flat report (cleared after the exchange confirms flat), or the session forgets the owner's symbol with the book instead of learning it from the exchange, so no belief is corrected. Prefer the second (the mechanism, not a log level), and check `known_open_symbols` users (`open_position_count`) first.
