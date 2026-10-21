# BUG-257 — A refused start during the exchange's pause logs an ERROR with a traceback for a ladder it never laid, and its reason line leads with `inventory_unavailable`

- **Reported:** 2026-10-21 (the reviewer of the `BUG-256` pull request, round 1, as a pre-existing finding; filed at the coordinator's request, for later)
- **Severity:** 🟢 P3 — wording and log level: a start refused during the exchange's pause logs an ERROR "taking the ladder off failed" with a traceback when no ladder exists, and the reason line names `inventory_unavailable` before the pause; nothing is lost
- **Status:** Open
- **Board:** A refused start that meets the exchange's pause (after `BUG-256`, any 429 or 418 on a later opening slice) tries to take its ladder off, which raises under the pause; `GridTaskGuard._park` logs it with `logger.exception` although the bot has laid no ladder, and the reason line reads "waiting: the budget was refused: inventory_unavailable; retry 1 of 5 in 32s" before it names the pause.
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
Not yet established beyond the reviewer's reading, at `master-warrior` 68e1227b: `GridTaskGuard._park` (`grid_task_guard.py`, the `except Exception` around `self._parking.park()`) logs every failure of the park with `logger.exception`, with no case for an exchange pause or for a bot that has no ladder; and the registration refusal `INVENTORY_UNAVAILABLE` (`owner_budget_registration.py`) that the park meets under the pause is what the reason line leads with. Both mechanisms predate `BUG-256`; its path (a refused start under a pause during the opening) now reaches them on every such pause.

## Fix
Pending.

## Regression test
Pending: the `BUG-256` journey with a log handler asserting no ERROR record and a reason that names the pause first.

## Verification
Not run.

## Suggested next steps
1. Decide with `logging-rule.md` the level of a park failure caused by the exchange's pause (the pause is already told once, `[exchange-pause]`). 2. Skip the ladder removal when `GridParking` knows the bot placed no ladder order, or say so. 3. Put the pause first in the reason line.
