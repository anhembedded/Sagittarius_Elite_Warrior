# BUG-223 — Starting a Futures Grid is refused: "Owner budget … refused: Futures order history could not be read: APIError(code=-4181): Invalid start time."

- **Reported:** 2026-10-17 (the owner, Futures Testnet `ETHUSDT`, bot `djwx0w`, master after #545 `5a2d0eb`; via the coordinator session)
- **Severity:** 🔴 P1 — a Futures Grid cannot be started on the affected machine; funds are untouched (nothing was placed)
- **Status:** ✅ Fixed (2026-10-17)
- **Board:** A Futures Start was refused with -4181 on the very first history read of a new run. Probable cause (inferred, not seen on the exchange): the read starts at the run's start, a moment ago, translated onto the exchange's clock by a one-off offset estimate; an estimate a little high puts the start ahead of the exchange's clock. Fix: the start sent keeps 5 s under the estimate of now and the rows before the asked start are dropped; the error now names the endpoint and window.
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (start) → trading (`src/modules/trading/`) → `adapters/binance/` (`futures_history_reader.py`, `history_window.py`), reached from `application/owner_position_deriver.py`
- **Environment:** the owner's Windows machine, Futures Testnet; master `5a2d0eb`. Reproduced on Linux against the fake exchange.

## Reproduction
1. A bot that ran, stopped (`STOPPED`), then Start again: the checkpoint belongs to the earlier run, so the position is derived in full from the new run's start (`owner_position_deriver.py` → `_start_of`), which is the moment the start was decided.
2. The history read begins at that moment translated onto the exchange's clock with the session's offset (`history_reads.span_ms`).

Expected: the start goes on. Actual: refused at the first history read.

## Symptom
```
OwnerPosition INFO  Position checkpoint for djwx0w belongs to another run; deriving in full.
OwnerPosition WARNING Owner budget for djwx0w refused: Futures order history could not be read: APIError(code=-4181): Invalid start time.
Bots.Screen   INFO  Start Fu_test_net refused
```
The same bot's derivation a moment earlier, from a checkpoint a little older than now, succeeded. The message did not say which of the calls behind "order history" (`allOrders`, `allAlgoOrders`) the exchange refused.

## Root cause
**Inferred; the refused call and the exact rule were not observed** (egress to `*.binance.*` is blocked here, and the owner's log names no endpoint). What the evidence fixes: the only thing that differed between the derivation that worked and the one that failed is the start of the read. A checkpoint start is minutes behind now; a fresh run's start is a few milliseconds behind it. The start sent is `since + timestamp_offset` (`history_reads.py` → `span_ms`), where the offset is measured once from the midpoint of one round trip and is wrong by up to half that trip (`BUG-200` found the same error at the other end of the window). A start that close to now plus an offset that is a little high is later than the exchange's own clock, and an exchange that refuses a start older than seven days (`BUG-173`) plausibly refuses a start in its future with the same code. `BUG-200` padded the end of a read by 5 s; the start had no such margin (`history_window.py` → `fetch_span`, commit `5a2d0eb`).

The net that was silent: the fake exchange modelled only the old-start rule, so no test sent a start ahead of the exchange's clock.

New evidence after the first diagnosis (the owner's DEBUG run after an app restart, 12:33 local): `[clock-offset] futures exchange clock is -127211 ms from this machine's` — the owner's PC runs about 127 s ahead of Binance — and the same Start then succeeded. The offset is applied (BUG-189), so a 127 s skew is not itself the fault; the refusal needs a start that lands ahead of the exchange's clock, which a run that began a moment ago plus a slightly high estimate does. The competing hypothesis, a stale or missing offset (the start then lands 127 s ahead), cannot arise through the readers' own path: a signed session measures its offset when opened (`binance_client_builder.py` → `new_client`), is reused for at most ten minutes (`venue_sessions.py` → `SESSION_MAX_AGE_SECONDS`) and measures again on a `-1021` (`BUG-221`). A step of the machine's clock inside those ten minutes would produce it and is **not covered** by this fix. The regression test runs with the owner's 127 s skew and without.

Clock-skew warning (asked by the coordinator): the pre-flight `clock-skew` check (warn above 500 ms, fail at 1000 ms) and the health probe belong to the headless host and the CLI (`run`, `preflight`); the desktop app runs neither, so a 127 s skew warned nothing there, by design. Signed requests are corrected by the offset, so the skew is harmless to them; what it touches is every time taken from the local clock. Whether the desktop app should warn at connect is a separate question, not part of this fix. Separately: the headless pre-flight fails a skew of 1000 ms or more although the offset already makes such a machine work; that rule predates `BUG-111`'s correction and is worth a look of its own.

## Fix
- `history_window.py`: `HistoryWindowRules.start_margin_ms` (Futures sets `START_MARGIN_MS`, 5 s) moves a start that is not that far before `until_ms` back to it; `rows_from` drops the rows stamped before the start that was asked for, so the read means what it did: from the run's start on, not from five seconds before.
- `futures_history_reader.py`: all four calls (`allOrders`, `allAlgoOrders`, `userTrades`, `income`) use the margin; the orders, algo orders and fills are filtered with `rows_from`; each call's failure now names its endpoint and the window sent (`GET /fapi/v1/allAlgoOrders (startTime=…, endTime=…) could not be read: …`), so the next refusal says which call and for what.
- Not changed: the Spot reader (its fake and its endpoints show no such rule; same mechanism if it ever appears: set `start_margin_ms`).

Known limit: the rows are told from the run's start by the same offset estimate, so an order the exchange stamped within the estimate's error after the run's start can be read as before it. A fresh run places no order before its budget is derived, and later derivations start from a checkpoint a minute back, so nothing is lost in practice; recorded here rather than hidden.

## Regression test
- `tests/integration/infrastructure/binance/test_history_readers_against_fake_server.py::test_a_futures_run_that_began_a_moment_ago_is_read_whatever_the_clock_error` — red before the fix with the owner's message (`APIError(code=-4181): Invalid start time.` from `futures_get_all_orders`), green after; the real reader over HTTP to the fake, a session whose offset was measured 1 s high, one order stamped before the run and one after; run with the clocks agreeing and with the machine 127 s ahead as on the owner's PC (both red on the code at `5a2d0eb`).
- Units: `test_history_readers.py` (the endpoint and window are in the error of each of the three refused calls; the start keeps the margin; rows before the start are dropped), `test_history_window.py` (the margin, `rows_from`).
- The fake exchange (`futures_routes.py`) now refuses a `startTime` later than its clock with -4181; the rule is inferred and says so.

## Verification
Red then green on the same test (above). `tests/unit/modules/trading` and `tests/integration/infrastructure/binance` pass; the commit tier (`ci-local.ps1 -SkipTests`) and `tests/unit/architecture` pass. **Not established:** that this is the rule the owner's exchange applied. If Start is still refused after this fix, the error now names the call and window; send that line.
