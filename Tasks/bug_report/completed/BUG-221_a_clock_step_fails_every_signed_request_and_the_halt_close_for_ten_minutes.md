# BUG-221 — After the machine clock stepped, every signed request answered -1021 for ten minutes, the halt's close included

- **Reported:** 2026-10-15 (owner, VPS journal of the headless `run` host, Futures Testnet bot goy5j8, ETHUSDT long)
- **Severity:** 🔴 P1 — a leveraged position could not be seen or closed for 11 minutes (00:11:05 to 00:22:56): the halt's cancel and close failed with the same error that blinded the liquidation-risk read.
- **Status:** ✅ Fixed (2026-10-15)
- **Board:** Signed requests failed with `-1021` for ten minutes after the clock stepped and the halt could not close the position. Cause: the session's clock offset was measured once at open and nothing re-measured it on `-1021` until the venue re-opened the session at 600 s. Fix: `ResilientSession` re-measures the offset on the client that made the request and sends that request once more; a second `-1021` is raised as `CLOCK_SKEW`.
- **Context:** Run a grid bot (`Docs/SPEC/SPEC-014_run_a_grid_bot.md`) → `src/modules/trading/` → `adapters/binance/` (`resilient_session.py`, `venue_sessions.py`, `binance_client_builder.py`)
- **Environment:** Linux VPS with NTP active, Futures Testnet; preflight measured 67–75 ms skew afterwards. master-warrior at 5ac84b3.

## Reproduction
1. Open a signed Futures session while the clocks agree.
2. Step the machine clock more than 1 s ahead of the exchange's, inside the ten minutes the session is kept.
3. Send any signed request. Expected: it succeeds. Actual: `APIError(code=-1021)` on every request until the session is re-opened.

Reproduced on the fake exchange (`ClockPolicy`, Binance's timestamp rule) by the tests below.

## Symptom
```
00:11:05 APIError(code=-1021): Timestamp for this request was 1000ms ahead of the server's time.
         (GetOpenPositionsQuery every ~2.5 s, GetAccountSummaryQuery every 5 s as clock_skew)
00:12:07 WARNING liquidation risk is unknown: position last read 65 s ago
00:14:07 ERROR   position could not be seen for more than 120 s ... halting [liquidation-risk]
         halted (position_unobservable); closing the position [halt-closes-position]
         Owner budget ... refused: positionRisk: -1021 / taking the ladder off failed
00:22:56 position 0
```
"1000ms ahead" is Binance's fixed wording for the rule, not the measured gap, so the constant says nothing about the app's offset arithmetic.

## Root cause
The offset is measured once per session, in `binance_client_builder.py::sync_timestamp_offset` (formerly `_sync_timestamp_offset`, called from `new_client`). `VenueSessions.signed` (`venue_sessions.py:103`) keeps the session for `SESSION_MAX_AGE_SECONDS = 600` and then opens a new one. Nothing handled `-1021`: `ExchangeCallPolicy._run` (`exchange_call_policy.py:137`) classifies it `FailureKind.OTHER` and raises, for Futures and Spot alike. The python-binance client adds `timestamp_offset` to every signed request, so a machine clock that stepped inside the 600 s window made every request of the venue's one shared session fail until the session aged out, which matches the position reaching 0 at 00:22:56. The halt path (`grid_parking.py::park`, `_close_position`) sends through the same cached session, so the close failed for the same reason. `connection_failure_exit_code.py` saying `-1021` "resyncs" described a recovery nothing performed.

Not a gate escape for a case study: no net compared a stepped clock with the session's cached reading (the fake exchange had no timestamp rule); the rule now exists in `ClockPolicy`.

## Fix
- `resilient_session.py`: on `-1021` the session calls its `resync_clock` (bound to the client that made the request), logs `[clock-resync]` at WARNING with the old and new offset, and sends the request once more. A second `-1021` is raised unchanged (`CLOCK_SKEW` path); no loop. Safe for an order submit: the exchange refuses the timestamp before it reads the order.
- `venue_sessions.py`: binds the resync to each signed client with the venue's API family (Futures `futures_time`, Spot `get_server_time`); the public session signs nothing and has none.
- `binance_client_builder.py`: the measurement is public (`sync_timestamp_offset`), one function for the open and the repair.
- `tests/sanity/fake_exchange/server.py`: `ClockPolicy`, Binance's timestamp rule, off by default.

## Regression test
- `tests/integration/infrastructure/binance/test_a_stepped_clock_is_measured_again_on_the_first_rejected_timestamp.py` (real python-binance `Client`, `FuturesSessionFactory`, loopback fake exchange): a read and a leverage change after a 3 s step succeed after one re-measure; a skew that cannot be cured (two `-1021` answers) raises `CLOCK_SKEW` after exactly two sends and one re-measure.
- `tests/integration/modules/bots/test_a_halt_closes_the_position_after_the_machine_clock_steps_on_the_fake_exchange.py`: the composed app halts on a silent feed after the step and ends flat.
- Red on the old tree for the right reason: `APIError(code=-1021)` raised; the halt test reproduced the owner's lines `Owner budget ... refused: positionRisk: -1021` and `taking the ladder off failed`, bot left `STOPPING` with the position open. Green after.

## Verification
Regression tests green after the fix (positive proof in the log: `Exchange rejected the timestamp of futures_position_information (-1021); clock offset measured again (0 ms -> -2999 ms), sending it once more [clock-resync]`). Commit tier and architecture guards: see the pull request. Not run: the real testnet (the stepped clock is simulated).
