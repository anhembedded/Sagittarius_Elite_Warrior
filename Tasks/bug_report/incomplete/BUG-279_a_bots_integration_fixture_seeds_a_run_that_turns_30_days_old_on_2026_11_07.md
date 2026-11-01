# BUG-279 — the bots integration world seeds a run started 2026-10-08, which crosses the 30-day edge on 2026-11-07

- **Reported:** 2026-11-01 (coordinating session and the BUG-278 reviewer; found while fixing BUG-278)
- **Severity:** 🟡 P2 — `master-warrior` would go red again on 2026-11-07 if a test reads the real clock against it
- **Status:** Open
- **Board:** Same shape as `BUG-278`: `RUN_STARTED = datetime(2026, 10, 8, …)` (`tests/integration/modules/bots/bots_module_world.py:96`) is a fixed run start; it is 30 days old on 2026-11-07. Whether a test fails then is Not yet established.
- **Context:** Test fixtures → `tests/integration/modules/bots/` (also the other fixed `_AT`/`_NOW`/`EPOCH` dates listed below)
- **Environment:** Linux, Python 3.12, app commit `1ac6f28`, sandbox clock 2026-11-01

## Reproduction
Not yet reproduced. The real clock is needed; moving it with `faketime` does not work (see Symptom).

## Symptom
Not observed yet. Candidates, fixed dates in `tests/integration/modules/bots/`: `bots_module_world.py:96` (2026-10-08, used by `test_bots_module_price_watch_wiring.py`), `virtual_order_time.py:45` (2026-10-20), `_AT` in eight files (2026-10-08 … 2026-10-20). Whether each is read against the real clock, as opposed to an injected one, is not established.

`faketime -f +45d` over `tests/integration/modules/bots` gave 17 failures (16 timeouts, 1 leftover-thread assertion). They are **not** dates: the same files pass 36/36 in 22 s on the real clock, and `faketime -f +0d` (no shift) fails 14 of them.

## Root cause
Not yet established.

## Fix
Not yet done. Intended: relative dates (`datetime.now(UTC) - timedelta(days=1)`) where the code under test reads the real clock, an injected clock elsewhere; and a wider guard (replacing `test_a_process_test_seeds_its_run_start_from_the_clock.py`) that scans `tests/integration/**` and not only `run_started_at`.

## Regression test
Not run.

## Verification
Not run.

## Suggested next steps
Find which tests read `RUN_STARTED` and the `_AT` dates against the real clock; a cheap way is to move the date one test at a time to 40 days ago and see which fail on the real clock.
