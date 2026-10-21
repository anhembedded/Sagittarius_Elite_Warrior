# BUG-257 — A refused start during the exchange's pause logs an ERROR with a traceback for a ladder it never laid, and its reason line leads with `inventory_unavailable`

- **Reported:** 2026-10-21 (the reviewer of the `BUG-256` pull request, round 1, as a pre-existing finding; filed at the coordinator's request, for later)
- **Severity:** 🟢 P3 — wording and log level: a start refused during the exchange's pause logs an ERROR "taking the ladder off failed" with a traceback when no ladder exists, and the reason line names `inventory_unavailable` before the pause; nothing is lost
- **Status:** ✅ Fixed (2026-10-21)
- **Board:** The park of a start refused under the exchange's pause logged an ERROR with a traceback for a ladder never laid, and the stop's reason led with the code `inventory_unavailable`; the pause is now told once as INFO `[exchange-pause]`, a bot holding no order names none, and the refusal says the exchange asked for a pause.
- **Context:** Start a Grid (`Docs/SPEC/`) → bots (`src/modules/bots/`) → `application/kinds/grid/` (`grid_task_guard.py`, `grid_parking.py`), the stop's reason wording (`stop/`)
- **Environment:** `master-warrior` 68e1227b (after `BUG-256`), found by the reviewer in a probe copy of `test_an_exchange_pause_in_the_openings_later_slice_closes_the_start_on_the_fake_exchange.py` on the Futures fake. Not seen in the owner's runs.

## Reproduction
Run the journey above (a 429 on the connection check of the opening's second order) with the app's logging on, and read the bot's reason after the STOPPING check. Frequency: every pause that lands on a later opening slice; the same path is reached by any start refused while the exchange holds a pause.

## Symptom
```
ERROR Bot <id>: taking the ladder off failed   (traceback: the exchange's pause, RateLimitedApiException)
reason: waiting: the budget was refused: inventory_unavailable; retry 1 of 5 in 32s; ...
```
Expected: a pause is a DEBUG/INFO event (`[exchange-pause]`, as the tests in `test_a_pause_is_debug_and_a_real_failure_stays_an_error.py` say), the ladder removal is skipped or told as "nothing to take off" when the bot placed no ladder order, and the reason names the pause first.

## Root cause
Established at `68e1227` by reproducing `BUG-256`'s journey (a 429 on the order after the first opening slice) with the app's log captured:
- `GridTaskGuard._park` (`grid_task_guard.py`) caught every failure of `GridParking.park()` with `logger.exception` and the note "its orders may still rest: …", with no case for the exchange's pause (`ExchangeRateLimitedError`, already told as `[exchange-pause]`) and none for a bot that holds no order.
- The reason's lead came from the stop's registration: under the pause the position read fails and `OwnerPositionRegistrar` (and the Spot handler) refused with `INVENTORY_UNAVAILABLE`, losing the pause that caused it; `refusal_text` printed the enum's code.
- The gate was green because no journey read the app's log after a pause that lands on a refused start.

## Fix
- `grid_task_guard.py` `_pause_met_while_parking`: a pause during the park is INFO `[exchange-pause]`, not an ERROR; the note says orders may still rest only when the runtime holds some.
- `trading/application/exchange_pause_behind.py` finds the pause along an exception's causes; both registrars set `OwnerBudgetRegistrationResult.paused_for` on `INVENTORY_UNAVAILABLE`; `refusal_text` says "the exchange asked for a pause of N s, so its records could not be read", or "the exchange's records could not be read", never the code (the code stays in the log).

## Regression test
`tests/integration/modules/bots/test_a_pause_that_refuses_a_start_logs_no_error_on_the_fake_exchange.py` (no ERROR, the pause named in the first clause, no code, no "may still rest"; red before on the ERROR) and `tests/unit/modules/trading/application/test_exchange_pause_behind.py`. Two assertions that looked for the code in a reason now look for the words.

## Verification
Commit tier, `tests/unit/modules/bots`, `tests/unit/modules/trading`, `tests/integration/modules/bots` green locally. Not run on a real exchange.

