# BUG-233 — A healthy `CLOSE_AT_MARKET` stop of a Futures bot writes `WARNING Position state mismatch ... app believed open, exchange reports flat`

- **Reported:** 2026-10-19 (the reviewer of #580, by a probe on the Futures fake at `7e0afce`, and again at `159fbfd`)
- **Severity:** 🟢 P3. The stop is correct; the WARNING cries wolf at the end of every healthy stop, and the run-log scan treats WARNING as a failure.
- **Status:** Fixed (2026-10-20)
- **Board:** A Futures bot stopped with a close logged `WARNING Position state mismatch ... app believed open, exchange reports flat` after ending flat and STOPPED. Cause: the stop clears the owner's book at `STOP_CONFIRMED` before the closing fills and the account's flat report arrive, so nothing recognised the report as the owner's. Fix: `OwnerBooks` remembers a position owner that left, and the first flat report on its symbol is logged at DEBUG; any other mismatch still warns.
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
Read at `0ccc921` and reproduced on the Futures fake (the regression test, red before the fix with exactly the reported line).
- A budgeted owner's order never marks the symbol open (`execute_order/handler.py`), so the session learns the owner's position from the exchange's first report and holds the symbol in `known_open_symbols` (`trading_session_state.py` → `TradingSessionState.reconcile_position`).
- The stop closes with reduce-only orders, confirms the exchange shrank and reaches `grid_stop_sequence.py:179` (`_confirm` → `clear_owner_budget`), which removes the owner's book. The closing fills (`ORDER_TRADE_UPDATE`) and the account's flat report (`ACCOUNT_UPDATE`) reach the session after that.
- `position_state_reconciler.py:46` (`reconcile_position_state`) excuses a correction only while `OwnerBooks.has_owner_on(symbol)` (BUG-203's rule). The book is gone, so the `open → flat` correction fell through to the WARNING at line 59.
- Not what the suggested next steps guessed: the closing fills do not reach the book first (it is already cleared), so a mark set by the book's own fills never fires; the departure itself has to be remembered.

## Fix
- `OwnerBooks.clear_owner` remembers the symbol of each position book it drops (`_departed`); `OwnerBooks.take_departure` answers once and consumes it; a new book on the symbol and `clear()` (disable, Emergency Stop, a new session) forget it.
- `reconcile_position_state` asks it on a flat report: a disagreement it explains is logged at DEBUG (`[...] the budgeted owner that traded it closed and left`), any other still warns. The correction of `known_open_symbols` itself is unchanged, and no order, close or stop behaviour is touched (`open_position_count` reads the same set as before).
- Price paid, locked by a test and a docstring: a position the user closes by hand on that symbol after the owner left is quiet at DEBUG once, until a new book is installed or the session ends.
- `OwnerBooks` now has 17 public methods against the guideline's 15 (16 before; see BUG-203's note). Accepted again: splitting its read side is a refactor outside a classification fix.

## Regression test
- `tests/integration/modules/bots/test_a_healthy_close_at_market_stop_logs_no_warning_on_the_fake_exchange.py`: a LONG Futures Grid with a position, stopped with `CLOSE_AT_MARKET`, ends STOPPED and flat with no WARNING on `App.*`. Red before the fix (the reported line), green after.
- `tests/unit/modules/trading/application/test_position_state_reconciler.py`: the flat report after an owner left is not a warning; only the first one is excused; another symbol still warns; a new owner on the symbol ends the excuse.

## Verification
Both tests red before the fix and green after; mutation check (the departure not recorded in `clear_owner`) turns both red. Commit tier `ci-local.ps1 -SkipTests` PASS, `tests/unit/architecture`, `tests/unit/modules/trading` and the log-view guards green (3999). Positive proof the new mechanism ran: the DEBUG line `Position state for BTCUSDT is flat: the budgeted owner that traded it closed and left`. Full gate: the PR's GitHub Actions run. Not run on a live testnet.

## Suggested next steps
None for this report.
