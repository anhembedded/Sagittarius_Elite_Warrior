# BUG-142 — After one manual Spot order, every later order on that symbol is refused until trading is enabled again

- **Reported:** 2026-10-03 (ADR §1.3 of `EPIC-029` recorded it as a finding to verify; reproduced by the author session while executing `EPIC-029A`)
- **Severity:** 🟡 P2 — on a Spot desk, a user who buys BTC by hand cannot sell it back, nor buy more, from the app for the rest of the session; disabling and enabling trading is the only way out.
- **Status:** Open
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
Not yet fixed; the mechanism, by reading: `TradingSessionState.record_order_sent` adds the symbol to `known_open_symbols` on every non-reducing order (`trading_session_state.py`, `record_order_sent`), and `open_position_count` counts a symbol in that set as one open position. On Futures the user data stream corrects the set (`futures_user_data_stream.py` calls `reconcile_position_state`); on Spot nothing does, because Spot has no position, so the symbol stays "open" for the session and `MAX_POSITIONS_PER_SYMBOL` refuses every later order on it. A Spot SELL cannot be marked as reducing either: `ExecuteOrderCommand` refuses a reducing purpose off Futures.

It is not the owner-budget mechanism `EPIC-029A` built (a budgeted order is recorded in its owner book and never marks the symbol), so per the task it is filed, not fixed there.

## Fix
Not yet. The likely direction: the position-shaped signal limit has no meaning on a venue without positions, so on Spot either the symbol is not marked open, or the "open position" fact comes from the holdings the Spot stream already re-reads. The choice changes a safety gate and is the user's (`ONBOARDING.md` §7).

## Regression test
Not yet written in the suite; the scratch reproduction above becomes it, red first, with the fix.

## Verification
Not run beyond the scratch reproduction.

## Suggested next steps
- Decide whether a Spot manual order should be paced by `MIN_ORDER_INTERVAL` only, or by a holdings-derived "position" (one `TradingLimitContext` field), and fix `TradingSessionState`/the context accordingly.
- Confirm on Spot Testnet with the desk.
