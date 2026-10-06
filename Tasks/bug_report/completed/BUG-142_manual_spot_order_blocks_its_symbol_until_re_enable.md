# BUG-142 — After one manual Spot order, every later order on that symbol is refused until trading is enabled again

- **Reported:** 2026-10-03 (ADR §1.3 of `EPIC-029` recorded it as a finding to verify; reproduced by the author session while executing `EPIC-029A`)
- **Severity:** 🟡 P2 — on a Spot desk, a user who buys BTC by hand cannot sell it back, nor buy more, from the app for the rest of the session; disabling and enabling trading is the only way out.
- **Status:** ✅ Fixed (2026-10-06)
- **Context:** Spot desk manual order entry (`SPEC-013`, `SPEC-012`) → `src/modules/trading/` → `application/trading_session_state.py`, `domain/policies/trading_limit_policy.py`
- **Environment:** Linux container, Python 3.12, branch `claude/wizardly-cerf-fc5b5x` (`EPIC-029A`). Reproduced in a unit test of the real `ExecuteOrderCommandHandler`; not yet seen on Spot Testnet. No credentials involved.

## Reproduction
1. Enable trading on the Spot Testnet venue (default limits: `max_positions_per_symbol=1`; set `min_order_interval_seconds` to 0 to rule out the interval).
2. Send a manual MARKET BUY of BTCUSDT from the desk. It is accepted.
3. Send a manual SELL of BTCUSDT (or another BUY).
4. Expected: accepted, subject to the per-order notional and interval. Actual: refused with `MAX_POSITIONS_PER_SYMBOL`.

Frequency: every time, until the next enable (which re-seeds `known_open_symbols` from Futures positions, always empty on Spot).

## Symptom
Scratch reproduction through `ExecuteOrderCommandHandler` on `SPOT_TESTNET` (limits 20 / 500 / 1 / 0 s):
```
BUY blocked_by: None
known_open_symbols after BUY: {'BTCUSDT'}
SELL blocked_by: TradingLimitViolation.MAX_POSITIONS_PER_SYMBOL
```

## Root cause
`ExecuteOrderCommandHandler.execute` called `session_state.record_order_sent(symbol, now)` after every non-reducing, untagged live order (`handler.py:207` before the fix), and `TradingSessionState.record_order_sent` added the symbol to `known_open_symbols` (`trading_session_state.py:229` before the fix). `open_position_count` counts a symbol in that set as one open position, so `MAX_POSITIONS_PER_SYMBOL` (default 1) refused the next order. On Futures the user data stream corrects the set (`futures_user_data_stream.py` calls `reconcile_position_state`); on Spot nothing does, because Spot has no positions to reconcile, and a Spot SELL cannot be marked reducing (`ExecuteOrderCommand.__post_init__` refuses a reducing purpose off Futures). The position-shaped bookkeeping was applied to a venue with no positions.

It is not the owner-budget mechanism `EPIC-029A` built (a budgeted order is recorded in its owner book and never marks the symbol).

## Fix
The owner's decision (a safety gate, `ONBOARDING.md` §7): on a venue without positions an order does not mark its symbol open; Spot stays paced by the per-order notional, the session order count and the minimum order interval. Futures is unchanged.
- `TradingVenue.has_positions` (`trading_venue.py`): the one capability, true only for `FUTURES_TESTNET`.
- `TradingSessionState.record_order_sent(..., *, venue_has_positions=True)`: always counts the order and the symbol's interval, marks the symbol open only when the venue has positions.
- `ExecuteOrderCommandHandler` passes `command.venue.has_positions`. It is the only caller of `record_order_sent`, so no other path treats "an order sent" as "a position open" (grep of `record_order_sent` and `known_open_symbols` in `src/`); `reconcile_position` and `enable` seeding only ever receive Futures positions.

## Regression test
- `tests/unit/modules/trading/application/orders/test_execute_order_submission.py::TestAVenueWithoutPositionsNeverMarksASymbolOpen`, through the real `ExecuteOrderCommandHandler` and `TradingLimitPolicy`:
  - `test_a_second_order_on_the_same_spot_symbol_is_accepted`: red before the fix (`assert <TradingLimitViolation.MAX_POSITIONS_PER_SYMBOL> is None`), green after.
  - `test_a_spot_order_still_counts_against_the_session_and_the_interval`: red before (`'BTCUSDT' not in {'BTCUSDT'}`), green after; a second Spot order inside the interval is still refused with `MIN_ORDER_INTERVAL`.
  - `test_a_second_order_on_the_same_futures_symbol_is_still_refused`: Futures keeps refusing with `MAX_POSITIONS_PER_SYMBOL`.
- `test_trading_session_state.py::test_record_order_sent_on_a_venue_without_positions_counts_but_does_not_mark_open`, and `test_trading_venue.py::test_only_a_futures_venue_has_positions`.

## Verification
- Red before the fix: 2 failed, 1 passed (the Futures test) in the new class.
- Mutation checks: the handler always passing `True` fails 2 tests; the state ignoring the flag fails 3.
- `pytest tests/unit/modules/trading tests/unit/architecture`: 2434 passed (before the added unit tests); `tests/unit/modules/trading/application`, `tests/unit/support/binance_gateway` and `tests/integration/application`: 423 passed.
- Not run: Spot Testnet with the desk.
