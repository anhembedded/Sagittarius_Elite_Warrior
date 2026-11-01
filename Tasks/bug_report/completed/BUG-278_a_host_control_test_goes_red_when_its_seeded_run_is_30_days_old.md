# BUG-278 — `test_a_second_process_stops_a_bot_on_the_running_host_and_the_host_listens_on_no_port` goes red 30 days after its seeded run date

- **Reported:** 2026-11-01 (coordinating session; `master-warrior` and PR #753 red since 2026-10-31)
- **Severity:** 🔴 P1 — every pull request is blocked on a test, though the product is right
- **Status:** ✅ Fixed (2026-11-01)
- **Board:** Root cause: a test seeded a run started on a fixed date (2026-10-01) for a host process that reads the real clock; 30 days later the run is older than `MAX_HISTORY_LOOKBACK` and Stop reconciles another way. Fix: the seed starts the run one day before now; no `src/` change.
- **Context:** Control of a running host (`bot stop`) → `src/modules/trading/application/` → test only
- **Environment:** Linux, Python 3.12, app commit `f7176b3`, sandbox clock 2026-11-01

## Reproduction
1. On any date after 2026-10-31: `pytest tests/integration/presentation/test_control_of_a_running_host_process.py`.
2. Expected: 5 passed. Actual: 1 failed, 4 passed. Same on a clean `f7176b3`. Passed with the clock at 2026-10-29.

## Symptom
```
>       assert _state_of(bots, "aaaaaa") is BotLifecycleState.STOPPED
E       assert <BotLifecycleState.STOPPING: 'STOPPING'> is <BotLifecycleState.STOPPED: 'STOPPED'>
FAILED ...::test_a_second_process_stops_a_bot_on_the_running_host_and_the_host_listens_on_no_port
```

## Root cause
`_seed_a_bot_that_ran` (`test_control_of_a_running_host_process.py:101` at `f7176b3`) writes `run_started_at = 2026-10-01`. The host process is a real subprocess and reads the real clock. `checkpointed_replay.py:108` (`now - start.read_from > MAX_HISTORY_LOOKBACK`, 30 days, `i_account_history_reader.py:75`) takes the "no checkpoint covers it" path once the run is older than 30 days, so the Stop's reconcile does not finish and the bot stays `STOPPING`. The product is right (the venue's history really stops at 30 days); the test mixed a fixed instant with a real clock. Same family as `BUG-269` (`pitfalls/tests.md` #9).

## Fix
Test only: the run starts `datetime.now(UTC) - timedelta(days=1)`. Assertions unchanged. A guard (`tests/unit/architecture/test_a_process_test_seeds_its_run_start_from_the_clock.py`) fails an `integration/presentation` test that writes `run_started_at` and a fixed `datetime(202x, …)` literal in one file.

## Regression test
`tests/integration/presentation/test_control_of_a_running_host_process.py::test_a_second_process_stops_a_bot_on_the_running_host_and_the_host_listens_on_no_port` — red on `f7176b3` for the reason above; green after, also under `faketime -f +45d` and `+400d`.

## Verification
See the pull request.
