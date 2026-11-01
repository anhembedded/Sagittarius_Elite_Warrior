# BUG-279 — the VPS-tab host test seeds a bot created on a fixed date that falls out of the 30-day history window on 2026-11-26

- **Reported:** 2026-11-01 (coordinating session and the BUG-278 reviewer; found while fixing BUG-278)
- **Severity:** 🟡 P2 — `master-warrior` goes red again on 2026-11-26 for the same reason as `BUG-278`
- **Status:** ✅ Fixed (2026-11-01)
- **Board:** Root cause: `NOW = datetime(2026, 10, 27)` in the VPS-tab host test is the seeded bot's creation date, read against the real clock by the host; 30 days on, the history read is refused. Fix: `NOW` is one day before the real clock. The `RUN_STARTED = 2026-10-08` named in the first report is not date-sensitive.
- **Context:** VPS tab host (`bot refresh`) → `src/modules/trading/application/` history reads → test only
- **Environment:** Linux, Python 3.12, app commit `ead1b4a`, sandbox clock 2026-11-01

## Reproduction
Moving every fixed `datetime(2026, 10, …)` in `tests/integration/modules/bots` back one month (twelve literals in twelve files) and running that directory on the real clock: 454 passed, **1 failed**, `test_the_host_serves_the_vps_tab_on_the_fake_exchange.py::test_what_the_readers_read_is_published_in_the_reads_file_with_the_time_it_was_read` (`within 8 s: the host-reads file holds the planner inputs and the fills`). The same moved dates, with the file's `NOW` relative: 455 passed.

## Symptom
```
Failed: within 8 s: the host-reads file holds the planner inputs and the fills
1 failed, 454 passed in 141.73s
```
The file holds the planner inputs and fills only when the history read succeeds; it reads back to the bot's creation (`NOW`), and `MAX_HISTORY_LOOKBACK` is 30 days (`i_account_history_reader.py:75`, `checkpointed_replay.py:108`).

## Root cause
`NOW = datetime(2026, 10, 27, 9, 0, tzinfo=UTC)` (`test_the_host_serves_the_vps_tab_on_the_fake_exchange.py:85` at `ead1b4a`) is the bot's `created_at` and the tick time. The host reads the real clock. On 2026-11-26 it is 30 days old and the read is refused. Same family as `BUG-278`.

`RUN_STARTED = 2026-10-08` (`bots_module_world.py:96`), the date that started this report, is **not** date-sensitive: the experiment above moved it to 2026-09-08 and no test failed. The other fixed `_AT` / `EPOCH` dates in the directory are read against an injected clock.

## Fix
`NOW` is `datetime.now(UTC).replace(microsecond=0) - timedelta(days=1)`. Test only.

A structural guard was considered and not added: a fixed date is legitimate wherever the clock is injected (most of the 12 literals), so a literal scan needs an allowlist of every legitimate one and only moves the maintenance. The method that finds the real ones is the date-moving experiment above.

## Regression test
`tests/integration/modules/bots/test_the_host_serves_the_vps_tab_on_the_fake_exchange.py` — 4 passed after; the date-moved run is the red-before (above).

## Verification
- Date-moved run of `tests/integration/modules/bots` with the fix: 455 passed.
- Same experiment over the other `tests/integration` files with a fixed Sept/Oct date (8 files): 289 passed, 1 failed (`test_workbench_conformance[True-1024x700]`), which fails on the unmoved real clock too (a local environment difference, green in CI; not a date).
- The +45d `faketime` failures in `tests/integration/modules/bots` (16 timeouts, 1 leftover-thread assertion) are a harness artifact, not dates: `faketime -f +0d` fails 14 of the same 36 tests that pass in 22 s on the real clock.
